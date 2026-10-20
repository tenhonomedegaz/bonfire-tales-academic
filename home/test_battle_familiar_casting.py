"""Workshop common spell integration; run serially against isolated PostgreSQL."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.battle_familiar_casting import KEY, command_token, workshop_context
from home.models import TbMagia, TbRecursoclasse, TbClassehabilidade
from home.resource_engine import activate_state


class BattleFamiliarCastingTests(TestCase):
    def setUp(self):
        from home.test_magic_workshop import MagicWorkshopTests
        MagicWorkshopTests.setUp(self)
        TbRecursoclasse.objects.create(id_classe=self.classe, nome='2°', slug='2o',
                                      valores_json={'3': '2'}, tipo='table-only')
        self.spell.nome = 'Familiar de Batalha'
        self.spell.nome_ingles = 'Battle Familiar'
        self.spell.nivel = 2
        self.spell.componentes = 'V, S, M (um diamante de pelo menos 25 PO)'
        self.spell.duracao = '1 hora'
        self.spell.save()
        self.owned = self.personagem.magias.create(
            id_magia=self.spell, nome=self.spell.nome, nivel=2,
            origem=self.classe.nome, preparada=True)
        self.focus = self.personagem.inventario.create(
            nome='Diamante', qtd=1, tags_json=[
                'spell_component{spell:fogo_de_teste, kind:focus, cost_po:25}'])
        self.url = reverse('oficina_conjurar_magia', args=[self.personagem.pk])
        self.end_url = reverse('oficina_encerrar_efeito', args=[self.personagem.pk])
        self.data = {
            'personagem': self.personagem.pk, 'magia_personagem': self.owned.pk,
            'slot': '2', 'familiar_form': 'bruto', 'familiar_existing': 'no',
            'familiar_type': 'Feérico', 'familiar_appearance': 'Lobo',
            'familiar_command': command_token(self.personagem), 'tab': 'casting',
        }
        self.client.force_login(self.user)

    def cast(self, **changes):
        return self.client.post(self.url, {**self.data, **changes})

    def state(self):
        return self.personagem.estados.get(chave=KEY)

    def base(self, *, complete=True):
        spell = TbMagia.objects.create(nome='Encontrar Familiar', nome_ingles='Find Familiar',
                                       slug='encontrar-familiar', nivel=1, ritual=True,
                                       tags_json=['log_castable'])
        payload = {'spell_id': spell.pk, 'spell_name': spell.nome, 'spell_slug': spell.slug,
                   'other_data': {'keep': [1, 2, 3]}}
        if complete:
            payload['find_familiar'] = {'form': 'Coruja', 'type': 'Celestial',
                'alignment': 'Caótico Bom', 'hp': 2, 'hp_max': 3, 'hit_dice': '1d4',
                'traits': 'Vínculo telepático; sentidos compartilhados; entregar magias de toque.'}
        return activate_state(self.personagem, 'spell:find', origin='magia:' + spell.slug,
                              payload=payload, ends_on=['dismissed'])

    def test_cast_uses_slot_and_retains_diamond_and_common_block(self):
        response = self.cast()
        self.assertIn('status=conjurada', response.url, self.client.session.get('battle_familiar_error'))
        payload = self.state().payload_json
        self.assertEqual((payload['hp'], payload['block']['ac']), (30, 15))
        self.assertEqual(payload['block']['rend_attack'], 5)
        self.assertFalse(payload['concentration'])
        self.assertEqual(payload['spending']['level'], 2)
        self.focus.refresh_from_db()
        self.assertEqual(self.focus.qtd, 1)
        resource = self.personagem.recursos.get(chave='spell_slot:2')
        self.assertEqual(resource.atual, resource.maximo - 1)

    def test_identity_and_form_appear_on_workshop(self):
        response = self.client.get(reverse('oficina_magia'), {'personagem': self.personagem.pk})
        self.assertContains(response, 'Battle Familiar')
        self.assertContains(response, 'name="familiar_form"')
        self.assertContains(response, 'name="familiar_command"')
        self.assertContains(response, 'Find Familiar existente')

    def test_repeated_post_never_spends_twice_even_after_end(self):
        self.cast()
        resources = list(self.personagem.recursos.values_list('chave', 'atual'))
        self.cast()
        self.assertEqual(list(self.personagem.recursos.values_list('chave', 'atual')), resources)
        self.assertEqual(self.personagem.transacoes.count(), 1)
        self.client.post(self.end_url, {'estado': KEY, 'familiar_revision': self.state().payload_json['revision']})
        self.cast()
        self.assertFalse(self.state().ativo)
        self.assertEqual(self.personagem.transacoes.count(), 1)

    def test_token_cannot_be_reused_with_changed_choices(self):
        self.cast()
        response = self.cast(familiar_form='voador')
        self.assertIn('familiar_invalido', response.url)
        self.assertEqual(self.state().payload_json['form'], 'bruto')
        self.assertEqual(self.personagem.transacoes.count(), 1)

    def test_missing_token_and_invalid_choices_do_not_spend(self):
        for changes in ({'familiar_command': ''}, {'familiar_form': 'dragon'}, {'slot': '1'},
                        {'slot': '10'}, {'slot': 'abc'}, {'ritual': '1'},
                        {'familiar_existing': ''}, {'familiar_type': 'Humanoide'}):
            with self.subTest(changes=changes):
                self.assertIn('familiar_invalido', self.cast(**changes).url)
                self.assertFalse(self.personagem.recursos.exists())
                self.assertFalse(self.personagem.estados.filter(chave=KEY).exists())

    def test_unavailable_slot_unprepared_and_missing_component_do_not_spend(self):
        self.assertIn('familiar_invalido', self.cast(slot='9').url)
        self.owned.preparada = False
        self.owned.save()
        self.assertIn('familiar_invalido', self.cast().url)
        self.owned.preparada = True
        self.owned.save()
        self.focus.delete()
        self.assertIn('familiar_invalido', self.cast().url)
        self.assertFalse(self.personagem.transacoes.exists())
        self.assertFalse(self.personagem.recursos.exists())

    def test_other_owner_and_staff_cannot_cast_or_update(self):
        self.cast()
        other = User.objects.create_user(username='familiar-other', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.cast().status_code, 404)
        response = self.client.post(self.end_url, {'estado': KEY,
            'familiar_revision': self.state().payload_json['revision']})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.state().ativo)

    def test_find_familiar_preserved_and_restored_at_zero_temp_hp(self):
        base = self.base()
        original = base.payload_json
        self.cast(familiar_form='voador')
        payload = self.state().payload_json
        self.assertEqual((payload['hp'], payload['hp_max'], payload['temp_hp']), (2, 3, 20))
        self.assertEqual(payload['type'], 'Celestial')
        self.assertEqual(payload['alignment'], 'Caótico Bom')
        self.assertEqual(payload['hit_dice'], '1d4')
        self.assertEqual(payload['traits'], original['find_familiar']['traits'])
        base.refresh_from_db()
        self.assertFalse(base.ativo)
        self.client.post(self.end_url, {'estado': KEY, 'familiar_action': 'hp',
            'familiar_hp': 0, 'familiar_revision': payload['revision']})
        base.refresh_from_db()
        self.assertTrue(base.ativo)
        self.assertEqual(base.payload_json, original)
        self.assertFalse(self.state().ativo)
        self.assertEqual(self.state().payload_json['temp_hp'], 0)

    def test_missing_base_is_explicit_and_only_missing_fields_are_requested(self):
        base = self.base(complete=False)
        self.assertIn('familiar_invalido', self.cast().url)
        self.assertFalse(self.personagem.recursos.exists())
        context = workshop_context(self.personagem)
        self.assertEqual(len(context['battle_familiar_missing']), 7)
        fields = {'form': 'Gato', 'type': 'Feérico', 'alignment': 'Neutro',
                  'hp': '1', 'hp_max': '2', 'hit_dice': '1d4', 'traits': 'Telepatia'}
        self.assertIn('conjurada', self.cast(**{'familiar_base_' + k: v for k, v in fields.items()}).url)
        base.refresh_from_db()
        self.assertEqual(base.payload_json['find_familiar']['form'], 'Gato')
        self.assertEqual(workshop_context(self.personagem)['battle_familiar_missing'], [])

    def test_expiration_restores_base_without_consuming_any_resource(self):
        base = self.base()
        before = base.payload_json
        self.cast()
        with patch('home.battle_familiar_casting.timezone.now', return_value=timezone.now() + timedelta(hours=2)):
            self.assertIsNone(workshop_context(self.personagem)['battle_familiar_state'])
        base.refresh_from_db()
        self.assertTrue(base.ativo)
        self.assertEqual(base.payload_json, before)
        self.assertFalse(self.state().ativo)
        self.assertEqual(self.personagem.transacoes.count(), 1)

    def test_recast_replaces_single_familiar_and_retains_original_base(self):
        base = self.base()
        original = base.payload_json
        self.cast()
        self.cast(familiar_form='espreitador', familiar_command=command_token(self.personagem))
        self.assertEqual(self.personagem.estados.filter(ativo=True, origem__startswith='magia:').count(), 1)
        self.assertEqual(self.state().payload_json['base_state']['payload'], original)
        self.assertEqual(self.state().payload_json['temp_hp'], 20)

    def test_stale_hp_form_does_not_damage_replacement(self):
        self.cast()
        old = self.state().payload_json['revision']
        self.cast(familiar_command=command_token(self.personagem))
        response = self.client.post(self.end_url, {'estado': KEY, 'familiar_action': 'hp',
            'familiar_hp': 0, 'familiar_revision': old})
        self.assertIn('familiar_invalido', response.url)
        self.assertTrue(self.state().ativo)
        self.assertEqual(self.state().payload_json['hp'], 30)

    def test_owner_death_does_not_restore_the_base(self):
        base = self.base()
        self.cast()
        self.client.post(self.end_url, {'estado': KEY, 'familiar_action': 'death',
            'familiar_revision': self.state().payload_json['revision']})
        self.assertFalse(self.state().ativo)
        base.refresh_from_db()
        self.assertFalse(base.ativo)

    def test_failure_after_spending_rolls_back_everything(self):
        with patch('home.battle_familiar.stat_block', side_effect=ValueError('bloco indisponível')):
            self.assertIn('familiar_invalido', self.cast().url)
        self.assertFalse(self.personagem.recursos.exists())
        self.assertFalse(self.personagem.estados.exists())
        self.assertFalse(self.personagem.transacoes.exists())

    def test_new_find_familiar_replaces_battle_familiar(self):
        base = self.base()
        self.cast()
        find_spell = TbMagia.objects.get(pk=base.payload_json['spell_id'])
        owned = self.personagem.magias.create(id_magia=find_spell, nome=find_spell.nome,
                    nivel=1, origem=self.classe.nome, preparada=True)
        response = self.client.post(self.url, {'personagem': self.personagem.pk,
                    'magia_personagem': owned.pk, 'ritual': '1'})
        self.assertIn('conjurada', response.url)
        self.assertFalse(self.state().ativo)
        self.assertEqual(self.personagem.estados.filter(ativo=True, origem__startswith='magia:').count(), 1)

    def test_render_active_familiar(self):
        self.cast(familiar_form='espreitador')
        response = self.client.get(reverse('oficina_magia'), {'personagem': self.personagem.pk})
        self.assertContains(response, 'Espreitar:')
        self.assertContains(response, 'testes de resistência acima já incluem')
        self.assertContains(response, 'Registrar PV restantes')

    def test_higher_slot_scales_from_paid_circle(self):
        pc = self.personagem.classes.get()
        pc.nivel = 7
        pc.save()
        TbRecursoclasse.objects.create(id_classe=self.classe, nome='4°', slug='4o',
                                      valores_json={'7': '1'}, tipo='table-only')
        self.assertIn('conjurada', self.cast(slot='4', familiar_form='espreitador').url)
        block = self.state().payload_json['block']
        self.assertEqual((block['circle'], block['hp_max'], block['multiattack']), (4, 30, 2))
        self.assertEqual(block['rend_damage'], '1d8+7')
        self.assertEqual(self.personagem.recursos.get(chave='spell_slot:4').atual, 0)

    def test_mystic_resource_contract_charges_actual_upcast_circle(self):
        feature = TbClassehabilidade.objects.get(id_classe=self.classe)
        feature.tags_json = [
            'spellcasting{ability:int, slots{progression:pact, resource:pontos_de_misticismo, cost:spell_level}, '
            'list:arquivista, mode:known, spell_level_limit{resource:ciclo}, pool:class_list}',
            'resource{pontos_de_misticismo}', 'resource_restore:pontos_de_misticismo=all(reset:short_rest)']
        feature.save()
        TbRecursoclasse.objects.create(id_classe=self.classe, nome='Pontos', slug='pontos-de-misticismo',
                                      valores_json={'1': '10'}, tipo='consumable', reset='short-rest')
        TbRecursoclasse.objects.create(id_classe=self.classe, nome='Ciclo', slug='ciclo',
                                      valores_json={'1': '4'}, tipo='table-only')
        self.assertIn('conjurada', self.cast(slot='4').url)
        self.assertEqual(self.state().payload_json['spending']['cost'], 4)
        self.assertEqual(self.state().payload_json['block']['circle'], 4)
        resource = self.personagem.recursos.get(nome='Pontos')
        self.assertEqual(resource.atual, 6)
        self.assertEqual(resource.chave, 'class:%s:0:pontos_de_misticismo' % self.classe.pk)
        rest = reverse('personagem_descansar', args=[self.personagem.pk])
        self.assertEqual(self.client.post(rest, {'tipo': 'curto'}).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 10)

    def test_explicit_existing_familiar_registration_rolls_back_on_missing_material(self):
        self.base(complete=False).delete()
        fields = {'form': 'Gato', 'type': 'Feérico', 'alignment': 'Neutro',
                  'hp': '1', 'hp_max': '2', 'hit_dice': '1d4', 'traits': 'Telepatia'}
        self.focus.delete()
        response = self.cast(familiar_existing='yes',
                            **{'familiar_base_' + k: v for k, v in fields.items()})
        self.assertIn('familiar_invalido', response.url)
        self.assertFalse(self.personagem.estados.exists())

    def test_legacy_battle_registration_is_replaced(self):
        old = activate_state(self.personagem, 'spell:legacy', origin='magia:' + self.spell.slug,
                             payload={'spell_id': self.spell.pk})
        self.cast()
        old.refresh_from_db()
        self.assertFalse(old.ativo)
        self.assertEqual(self.personagem.estados.filter(ativo=True).count(), 1)

    def primordial(self):
        from home.models import TbPersonagemCacador, TbRuleset
        ruleset = TbRuleset.objects.create(checksum='battle-familiar-guard-test', manifest={},
            evaluator_version='test', vocabulary_version='test')
        return TbPersonagemCacador.objects.create(
            personagem_classe=self.personagem.classes.get(), ruleset=ruleset, ability='int',
            companion={'active': True, 'summon_id': 'existing-primordial', 'hp': 12})

    def test_active_primordial_blocks_common_cast_without_spending(self):
        profile = self.primordial()
        original = dict(profile.companion)
        with patch('home.views._oficina_casting_resource') as spend:
            response = self.cast()
        self.assertIn('familiar_invalido', response.url)
        spend.assert_not_called()
        self.assertIn('painel Hunter', self.client.session['battle_familiar_error'])
        self.assertFalse(self.personagem.recursos.exists())
        self.assertFalse(self.personagem.estados.exists())
        self.assertFalse(self.personagem.transacoes.exists())
        self.focus.refresh_from_db()
        self.assertEqual(self.focus.qtd, 1)
        profile.refresh_from_db()
        self.assertEqual(profile.companion, original)
        self.assertEqual(profile.version, 0)

    def test_active_primordial_blocks_legacy_find_familiar_without_spending(self):
        profile = self.primordial()
        original = dict(profile.companion)
        base = self.base()
        find_spell = TbMagia.objects.get(pk=base.payload_json['spell_id'])
        base.delete()
        find_spell.componentes = 'M (incenso de 10 PO, consumido pela magia)'
        find_spell.save()
        material = self.personagem.inventario.create(nome='Incenso', qtd=1,
            tags_json=['spell_component{spell:encontrar_familiar, kind:consumable, cost_po:10}'])
        owned = self.personagem.magias.create(id_magia=find_spell, nome=find_spell.nome,
            nivel=1, origem=self.classe.nome, preparada=True)
        with patch('home.views._oficina_casting_resource') as spend:
            response = self.client.post(self.url, {'personagem': self.personagem.pk,
                'magia_personagem': owned.pk, 'slot': '2'})
        self.assertIn('familiar_invalido', response.url)
        spend.assert_not_called()
        self.assertIn('painel Hunter', self.client.session['battle_familiar_error'])
        self.assertFalse(self.personagem.recursos.exists())
        self.assertFalse(self.personagem.estados.exists())
        self.assertFalse(self.personagem.transacoes.exists())
        material.refresh_from_db()
        self.assertEqual(material.qtd, 1)
        profile.refresh_from_db()
        self.assertEqual(profile.companion, original)
        self.assertEqual(profile.version, 0)
