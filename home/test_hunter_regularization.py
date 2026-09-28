from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.management import call_command
from io import StringIO
import json
from copy import deepcopy
from unittest.mock import patch

from .content_versions import create_revision, seal_ruleset, resolve_content
from .character_engine import _magias_personagem
from .models import (TbClasse, TbClassehabilidade, TbSubclasse, TbPersonagem,
                     TbPersonagemClasse, TbPersonagemCacador, TbPersonagemMagia, TbMagia,
                     TbPersonagemItem, TbPersonagemAventura, TbOpcaojogo)
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class
from .hunter_regularization import REQUIRED_REPLACEMENTS
from .versioned_spells import snapshot_spells
from .test_criador import _CriadorBase
from .test_creator_hunter_binding import CreatorHunterBindingTests
from .hunter_catalog import compose_order_revision


class HunterRegularizationPreviewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='preview-owner')
        self.other = get_user_model().objects.create_user(username='preview-other')
        self.hunter = TbClasse.objects.create(nome='Caçador', slug='cacador')
        self.order = TbSubclasse.objects.create(id_classe=self.hunter,
            nome='Ordem Candidata', slug='ordem-candidata')
        TbClassehabilidade.objects.create(id_classe=self.hunter, nome='Habilidade antiga',
            descricao='Texto antigo', niveladquirido=1)
        TbClassehabilidade.objects.create(id_classe=self.hunter, id_subclasse=self.order,
            nome='Poder da Ordem', descricao='Só no catálogo vinculado', niveladquirido=3)
        self.person = TbPersonagem.objects.create(dono=self.owner, nome='Caçadora',
            nivel=3, carteira_pc=1234, aventuras=7, braseiros=9)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.hunter, nivel=3, principal=True)
        self.spell = TbPersonagemMagia.objects.create(id_personagem=self.person,
            nome='Magia conquistada', nivel=2, preparada=True, origem='Aventura')
        self.ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.hunter.pk, inventory_class(self.hunter.pk)),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        TbClassehabilidade.objects.filter(id_classe=self.hunter).update(
            nome='Habilidade atual alterada', descricao='Texto atual')
        self.url = reverse('hunter_regularization_preview', args=[self.person.pk])

    def test_owner_sees_comparison_and_existing_assets_remain_untouched(self):
        self.client.force_login(self.owner)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Habilidade atual alterada')
        self.assertContains(response, 'Habilidade antiga')
        self.assertContains(response, 'Inteligência ou Sabedoria')
        self.assertContains(response, 'Magia conquistada')
        self.assertContains(response, '1234 PC')
        self.assertFalse(TbPersonagemCacador.objects.exists())
        self.person.refresh_from_db()
        self.spell.refresh_from_db()
        self.assertEqual((self.person.carteira_pc, self.person.aventuras, self.person.braseiros),
                         (1234, 7, 9))
        self.assertEqual((self.spell.nome, self.spell.preparada), ('Magia conquistada', True))

    def test_order_candidate_is_read_only_and_restricted_to_snapshot(self):
        self.client.force_login(self.owner)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            response = self.client.get(self.url, {'order': self.order.pk})
            self.assertContains(response, 'Poder da Ordem')
            self.assertContains(response, 'Ordem Candidata')
            self.assertEqual(self.client.get(self.url, {'order': 999999}).status_code, 200)
            self.assertContains(self.client.get(self.url, {'order': 999999}),
                'Selecione uma Ordem da revisão de destino.')
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.id_subclasse_id)
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_owner_only_and_bound_hunter_not_eligible(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.owner)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            response = self.client.get(self.url)
        self.assertContains(response, 'ainda não está configurada')
        TbPersonagemCacador.objects.create(personagem_classe=self.pc,
            ruleset=self.ruleset, ability='int')
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unmapped_draft_order_can_be_previewed_but_never_applied(self):
        self.client.force_login(self.owner)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            response = self.client.post(self.url, {
                'ruleset_checksum': self.ruleset.checksum, 'expected_level': '3',
                'expected_order_id': '', 'order': str(self.order.pk),
                'ability': 'wis', 'confirm': '1'})
        self.assertContains(response, 'Escolha uma Ordem da revisão.')
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.id_subclasse_id)
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_acquired_spell_outside_revision_stays_visible_but_inactive(self):
        eligible = TbMagia.objects.create(nome='Magia da revisão', slug='magia-da-revisao', nivel=1)
        frozen = seal_ruleset([snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        removed = TbMagia.objects.create(nome='Magia depois da revisão', slug='magia-depois', nivel=2)
        self.spell.id_magia = removed
        self.spell.save(update_fields=['id_magia'])
        retained = TbPersonagemMagia.objects.create(id_personagem=self.person,
            id_magia=eligible, nome='Magia da revisão', nivel=1, preparada=True)
        rows = _magias_personagem(self.person, ruleset=frozen)
        by_name = {row['nome']: row for row in rows}
        self.assertFalse(by_name[self.spell.nome]['preparada'])
        self.assertTrue(by_name[self.spell.nome]['preparada_legada'])
        self.assertTrue(by_name[self.spell.nome]['suspensa_na_revisao'])
        self.assertTrue(by_name[retained.nome]['preparada'])
        self.assertFalse(by_name[retained.nome]['suspensa_na_revisao'])
        self.spell.refresh_from_db()
        self.assertTrue(self.spell.preparada)
        self.assertEqual(self.spell.id_magia_id, removed.pk)


class HunterRegularizationApplyTests(_CriadorBase):
    setup_creation = CreatorHunterBindingTests.setup_creation

    def _ready_ruleset(self, ruleset):
        # Exercise the binding gate with a sealed marker-complete test revision;
        # this does not claim that the release catalog has passed its review.
        identity = 'class-catalog:%s' % self.classe.pk
        payload = deepcopy(resolve_content(ruleset, identity,
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY))
        hunter = resolve_content(ruleset, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        for marker in REQUIRED_REPLACEMENTS:
            payload.setdefault(marker, {'source_sha256': hunter['source_sha256']})
        payload['hunter_mark_replacement'].update(version=1, duration_seconds=3600)
        revision = create_revision(identity, payload, dependencies=['hunter-rework'])
        others = [entry.revision for entry in ruleset.entries.select_related('revision')
                  if entry.identity != identity]
        return seal_ruleset(others + [revision], evaluator_version=EVALUATOR,
                            vocabulary_version=VOCABULARY)

    def _legacy_person(self):
        person = TbPersonagem.objects.create(dono=self.user, nome='Caçador antigo',
            nivel=1, carteira_pc=2345, aventuras=4, braseiros=6,
            pv_maximo=20, pv_atual=9)
        pc = TbPersonagemClasse.objects.create(id_personagem=person,
            id_classe=self.classe, nivel=1, principal=True)
        return person, pc

    def test_explicit_application_preserves_acquisitions_and_is_once_only(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        acquired = TbMagia.objects.create(nome='Magia comprada depois',
            slug='comprada-depois', nivel=1)
        owned = TbPersonagemMagia.objects.create(id_personagem=person,
            id_magia=acquired, nome=acquired.nome, nivel=1,
            preparada=True, origem=self.classe.nome)
        possession = TbPersonagemItem.objects.create(id_personagem=person,
            nome='Lembrança de aventura', qtd=2, origem_tipo='legado')
        history = TbPersonagemAventura.objects.create(id_personagem=person,
            nome_aventura='Missão antiga', qtd_aventuras=4, ouro_pago_pc=345,
            braseiros_pago=6)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '1', 'expected_order_id': '',
            'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertEqual(preview.status_code, 200)
            self.assertContains(preview, 'Confirmar regularização')
            response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302, response.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual((profile.ability, profile.ruleset_id), ('wis', self.ruleset.pk))
        self.assertEqual(profile.regularization['old_level'], 1)
        person.refresh_from_db()
        owned.refresh_from_db()
        self.assertEqual((person.carteira_pc, person.aventuras, person.braseiros), (2345, 4, 6))
        self.assertEqual(person.pv_atual, max(0, person.pv_maximo - 11))
        self.assertEqual((owned.id_magia_id, owned.preparada), (acquired.pk, True))
        self.assertEqual(list(person.inventario.values_list('pk', 'nome', 'qtd')),
                         [(possession.pk, 'Lembrança de aventura', 2)])
        self.assertEqual(list(person.aventuras_ledger.values_list(
            'pk', 'nome_aventura', 'qtd_aventuras', 'ouro_pago_pc', 'braseiros_pago')),
            [(history.pk, 'Missão antiga', 4, 345, 6)])
        self.assertEqual(TbPersonagemCacador.objects.filter(personagem_classe=pc).count(), 1)
        linked = self.client.get(reverse('hunter_sheet', args=[person.pk]))
        self.assertEqual(linked.status_code, 200)
        self.assertContains(linked, 'aquisição preservada; indisponível nesta revisão')
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            self.assertEqual(self.client.post(url, payload).status_code, 404)

    def test_inventory_or_adventure_mutation_rolls_back_regularization(self):
        from .hunter_views import linked_sheet_context

        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        item = TbPersonagemItem.objects.create(id_personagem=person,
            nome='Troféu antigo', qtd=2, origem_tipo='legado')
        history = TbPersonagemAventura.objects.create(id_personagem=person,
            nome_aventura='Caçada antiga', qtd_aventuras=4)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '1', 'ability': 'int', 'confirm': '1'}

        for model, pk, field, changed, message in (
                (TbPersonagemItem, item.pk, 'qtd', 9, 'inventário existente'),
                (TbPersonagemAventura, history.pk, 'qtd_aventuras', 9,
                 'histórico de aventuras')):
            def mutate_and_render(character, profile):
                model.objects.filter(pk=pk).update(**{field: changed})
                return linked_sheet_context(character, profile)

            with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
                with patch('home.hunter_views.linked_sheet_context',
                           side_effect=mutate_and_render):
                    response = self.client.post(url, payload)
            self.assertContains(response, message)
            self.assertFalse(TbPersonagemCacador.objects.filter(
                personagem_classe=pc).exists())
            pc.refresh_from_db()
            self.assertIsNone(pc.id_subclasse_id)

        item.refresh_from_db()
        history.refresh_from_db()
        self.assertEqual((item.qtd, history.qtd_aventuras), (2, 4))

    def test_unmapped_class_choice_and_stale_preview_do_not_bind(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '1', 'ability': 'int', 'confirm': '1'}
        choice = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo_luta', valor='estilo-antigo')
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            blocked = self.client.post(url, payload)
            self.assertContains(blocked, 'sem mapeamento')
            choice.delete()
            payload['expected_level'] = '2'
            stale = self.client.post(url, payload)
            self.assertContains(stale, 'mudou desde a prévia')
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())
        pc.refresh_from_db()
        person.refresh_from_db()
        self.assertIsNone(pc.id_subclasse_id)
        self.assertEqual((person.carteira_pc, person.pv_atual), (2345, 9))

    def test_incomplete_target_cannot_bind_legacy_character(self):
        self.setup_creation()
        person, pc = self._legacy_person()
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '1', 'ability': 'int', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'ainda não possui todas as substituições')
            response = self.client.post(url, payload)
            self.assertContains(response, 'ainda não possui todas as substituições')
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

    def test_exact_legacy_style_requires_confirmation_and_transfers_once(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        option = TbOpcaojogo.objects.get(slug='test-hunter-style')
        old_choice = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo_luta', slot=0, id_opcao=option, valor=option.slug)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'Correspondência exata na revisão')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            self.assertContains(self.client.post(url, payload),
                'Confirme a transferência do Estilo de Luta antigo.')
            self.assertFalse(TbPersonagemCacador.objects.filter(
                personagem_classe=pc).exists())
            payload['confirm_style_id'] = str(old_choice.pk)
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertFalse(person.escolhas.filter(pk=old_choice.pk).exists())
        self.assertEqual(profile.regularization['transferred_style']['choice']['id'],
                         old_choice.pk)
        new_choice = person.escolhas.get(tipo='hunter-style')
        self.assertEqual(json.loads(new_choice.valor)['id'], option.pk)
        self.assertEqual(self.client.get(reverse('hunter_sheet', args=[person.pk])).status_code, 200)

    def test_style_already_owned_elsewhere_rolls_back_transfer(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        option = TbOpcaojogo.objects.get(slug='test-hunter-style')
        old_choice = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo_luta', slot=0, id_opcao=option, valor=option.slug)
        other_choice = person.escolhas.create(origem='Talento externo',
            tipo='estilo', slot=0, id_opcao=option, valor=option.slug)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1',
            'confirm_style_id': str(old_choice.pk)}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            rejected = self.client.post(url, payload)
        self.assertContains(rejected, 'não pode ser transferido nesta revisão')
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())
        self.assertTrue(person.escolhas.filter(pk=old_choice.pk).exists())
        self.assertTrue(person.escolhas.filter(pk=other_choice.pk).exists())
        self.assertFalse(person.escolhas.filter(tipo='hunter-style').exists())

    def test_removed_legacy_style_origin_blocks_ambiguity_and_allows_exact_transfer(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = pc.nivel = 2
        person.save(update_fields=['nivel'])
        pc.save(update_fields=['nivel'])
        self.assertFalse(TbClassehabilidade.objects.filter(
            id_classe=self.classe, nome='Estilo de Luta').exists())
        old = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo', slot=0, valor='estilo-sem-identidade')
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertEqual([row['id'] for row in preview.context['comparison'][
                'unresolved_class_choices']], [old.pk])
            rejected = self.client.post(url, payload)
            self.assertContains(rejected, 'sem mapeamento')
            self.assertFalse(TbPersonagemCacador.objects.filter(
                personagem_classe=pc).exists())
            self.assertTrue(person.escolhas.filter(pk=old.pk).exists())

            option = TbOpcaojogo.objects.get(slug='test-hunter-style')
            old.id_opcao = option
            old.valor = option.slug
            old.save(update_fields=['id_opcao', 'valor'])
            preview = self.client.get(url)
            self.assertIsNotNone(preview.context['comparison']['style_transfer'])
            self.assertFalse(preview.context['comparison']['unresolved_class_choices'])
            payload['confirm_style_id'] = str(old.pk)
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(profile.regularization['transferred_style']['choice']['id'],
                         old.pk)
        self.assertFalse(person.escolhas.filter(pk=old.pk).exists())
        self.assertEqual(person.escolhas.filter(tipo='hunter-style').count(), 1)

    def test_exact_legacy_secret_requires_confirmation_and_preparation(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Segredos de Caçador', niveladquirido=2)
        secret = resolve_content(self.ruleset, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)['secrets'][0]
        old = person.escolhas.create(origem='Segredos de Caçador',
            tipo='segredo', valor=secret['id'])
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1',
            'secret': [secret['id']]}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'identidade exata')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            self.assertContains(self.client.post(url, payload),
                                'Confirme a transferência de cada Segredo antigo')
            payload['confirm_secret_id'] = [str(old.pk)]
            no_preparation = dict(payload, secret=[])
            self.assertContains(self.client.post(url, no_preparation),
                                'Prepare os Segredos antigos correspondentes')
            self.assertTrue(person.escolhas.filter(pk=old.pk).exists())
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(profile.selected, [secret['id']])
        self.assertEqual(profile.regularization['transferred_secrets'][0]['choice']['id'],
                         old.pk)
        self.assertFalse(person.escolhas.filter(pk=old.pk).exists())

    def test_legacy_secret_without_exact_identity_stays_blocked(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Segredos de Caçador', niveladquirido=2)
        person.escolhas.create(origem='Segredos de Caçador',
            tipo='segredo', valor='nome-parecido-mas-diferente')
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            response = self.client.post(url, {'ruleset_checksum': self.ruleset.checksum,
                'expected_level': '2', 'ability': 'wis', 'confirm': '1'})
        self.assertContains(response, 'sem mapeamento')
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

    def test_style_and_secret_transfer_together_without_losing_either(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Segredos de Caçador', niveladquirido=2)
        secret = resolve_content(self.ruleset, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)['secrets'][0]
        old_secret = person.escolhas.create(origem='Segredos de Caçador',
            tipo='segredo', valor=secret['id'])
        option = TbOpcaojogo.objects.get(slug='test-hunter-style')
        old_style = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo_luta', slot=0, id_opcao=option, valor=option.slug)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'Correspondência exata na revisão')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            applied = self.client.post(url, {'ruleset_checksum': self.ruleset.checksum,
                'expected_level': '2', 'ability': 'wis', 'confirm': '1',
                'secret': [secret['id']], 'confirm_secret_id': [str(old_secret.pk)],
                'confirm_style_id': str(old_style.pk)})
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(profile.selected, [secret['id']])
        self.assertEqual(profile.regularization['transferred_style']['choice']['id'],
                         old_style.pk)
        self.assertEqual(profile.regularization['transferred_secrets'][0]['choice']['id'],
                         old_secret.pk)
        self.assertFalse(person.escolhas.filter(pk__in=[old_style.pk, old_secret.pk]).exists())
        self.assertTrue(person.escolhas.filter(tipo='hunter-style').exists())

    def test_level_three_requires_explicit_order_and_uses_pinned_choice(self):
        self.setup_creation()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        target = compose_order_revision(self.ruleset, class_id=self.classe.pk,
                                        order_ids=orders)
        target = self._ready_ruleset(target)
        person, pc = self._legacy_person()
        person.nivel = 3
        person.save(update_fields=['nivel'])
        pc.nivel = 3
        pc.save(update_fields=['nivel'])
        url = reverse('hunter_regularization_preview', args=[person.pk])
        self.client.force_login(self.user)
        payload = {'ruleset_checksum': target.checksum, 'expected_level': '3',
            'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            missing = self.client.post(url, payload)
            self.assertContains(missing, 'Escolha uma Ordem da revisão.')
            self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())
            payload['order'] = str(orders['ordem-da-alianca-selvagem'])
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        pc.refresh_from_db()
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(pc.id_subclasse_id, orders['ordem-da-alianca-selvagem'])
        self.assertEqual(profile.regularization['old_order_id'], None)
        self.assertEqual(profile.ruleset_id, target.pk)
        self.assertEqual(self.client.get(reverse('hunter_sheet', args=[person.pk])).status_code, 200)

    def test_exact_favored_enemy_requires_confirmation_and_keeps_assets(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = 2
        person.save(update_fields=['nivel'])
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Inimigo Favorito', niveladquirido=2)
        old = person.escolhas.create(origem='Inimigo Favorito',
            tipo='tipo_criatura', valor='Bestas')
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1'}
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'identidade exata de Bestas')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            self.assertContains(self.client.post(url, payload),
                                'Confirme a transferência de cada Inimigo Favorito')
            self.assertTrue(person.escolhas.filter(pk=old.pk).exists())
            payload['confirm_favored_id'] = [str(old.pk)]
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        from .hunter_choices import favored_state
        self.assertEqual(favored_state(profile)['selected'], ['bestas'])
        self.assertEqual(profile.regularization['transferred_favored'][0]['choice']['id'], old.pk)
        self.assertFalse(person.escolhas.filter(pk=old.pk).exists())
        self.assertEqual(person.escolhas.filter(tipo='hunter-favored').count(), 1)
        person.refresh_from_db()
        self.assertEqual((person.carteira_pc, person.aventuras, person.braseiros),
                         (2345, 4, 6))

    def test_legacy_favored_excess_requires_active_choice_and_unlocks_at_eight(self):
        self.setup_creation()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        target = compose_order_revision(self.ruleset, class_id=self.classe.pk,
                                        order_ids=orders)
        target = self._ready_ruleset(target)
        person, pc = self._legacy_person()
        person.nivel = 6
        person.save(update_fields=['nivel'])
        pc.nivel = 6
        pc.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Inimigo Favorito', niveladquirido=2)
        first = person.escolhas.create(origem='Inimigo Favorito',
            tipo='tipo_criatura', slot=0, valor='Bestas')
        second = person.escolhas.create(origem='Inimigo Favorito',
            tipo='tipo_criatura', slot=1, valor='Dragões')
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': target.checksum, 'expected_level': '6',
            'ability': 'wis', 'confirm': '1',
            'order': str(orders['ordem-da-alianca-selvagem']),
            'confirm_favored_id': [str(first.pk), str(second.pk)]}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'Escolha 1 tipo(s) antigo(s)')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            self.assertContains(self.client.post(url, payload),
                                'Escolha quais Inimigos Favoritos antigos ficam ativos')
            self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())
            payload['active_favored_id'] = [str(first.pk)]
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        from .hunter_choices import favored_state
        self.assertEqual(favored_state(profile)['selected'], ['bestas'])
        self.assertEqual(profile.regularization['deferred_favored'], ['dragoes'])
        self.assertEqual(person.escolhas.filter(tipo='hunter-favored').count(), 1)
        self.assertFalse(person.escolhas.filter(pk__in=[first.pk, second.pk]).exists())
        self.assertContains(self.client.get(reverse('hunter_preparation', args=[person.pk])),
                            'Inimigos Favoritos antigos preservados')
        pc.nivel = 8
        pc.save(update_fields=['nivel'])
        person.nivel = 8
        person.save(update_fields=['nivel'])
        profile.refresh_from_db()
        self.assertEqual(favored_state(profile)['selected'], ['bestas', 'dragoes'])
        self.assertEqual(person.escolhas.filter(tipo='hunter-favored').count(), 1)
        pc.nivel = 14
        pc.save(update_fields=['nivel'])
        person.nivel = 14
        person.save(update_fields=['nivel'])
        profile.refresh_from_db()
        from .hunter_choices import save_favored
        save_favored(character_id=person.pk, owner_id=self.user.pk,
            selected=['bestas', 'dragoes', 'celestiais'],
            expected_version=profile.version)
        profile.refresh_from_db()
        self.assertEqual(set(favored_state(profile)['selected']),
                         {'bestas', 'dragoes', 'celestiais'})
        self.assertEqual(person.escolhas.filter(tipo='hunter-favored').count(), 2)

    def test_exact_legacy_weapon_masteries_transfer_without_duplicate_effects(self):
        from .hunter_masteries import available_options, state as mastery_state
        from .character_engine import _maestrias_armas

        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = pc.nivel = 2
        person.save(update_fields=['nivel'])
        pc.save(update_fields=['nivel'])
        options = available_options(person, self.ruleset)
        values = []
        for option in options:
            if option['value'].split('|')[0] not in {v.split('|')[0] for v in values}:
                values.append(option['value'])
            if len(values) == 3:
                break
        self.assertEqual(len(values), 3)
        old = [person.escolhas.create(origem='Maestria de Arma (Caçador)',
            tipo='maestria', slot=slot, valor=value)
            for slot, value in enumerate(values)]
        self.assertEqual(len(_maestrias_armas(person, ruleset=self.ruleset)), 3)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '2', 'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertEqual(len(preview.context['comparison']['mastery_transfers']), 3)
            self.assertNotContains(preview, 'Estas escolhas impedem')
            rejected = self.client.post(url, payload)
            self.assertContains(rejected, 'Confirme a transferência de cada Maestria')
            self.assertEqual(person.escolhas.filter(pk__in=[row.pk for row in old]).count(), 3)
            payload['confirm_mastery_id'] = [str(row.pk) for row in old]
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(mastery_state(profile)['selected'], values)
        self.assertEqual([row['choice']['id'] for row in
            profile.regularization['transferred_masteries']], [row.pk for row in old])
        self.assertFalse(person.escolhas.filter(pk__in=[row.pk for row in old]).exists())
        self.assertEqual(len(_maestrias_armas(person, ruleset=self.ruleset)), 3)
        self.assertEqual(person.escolhas.filter(tipo='hunter-mastery').count(), 3)
        self.assertFalse(mastery_state(profile)['can_replace'])

    def test_ambiguous_legacy_weapon_mastery_remains_blocked(self):
        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        person.nivel = pc.nivel = 2
        person.save(update_fields=['nivel'])
        pc.save(update_fields=['nivel'])
        old = person.escolhas.create(origem='Maestria de Arma (Caçador)',
            tipo='maestria', slot=0, valor='arma-sem-identidade')
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'Estas escolhas impedem')
            response = self.client.post(url, {'ruleset_checksum': self.ruleset.checksum,
                'expected_level': '2', 'ability': 'wis', 'confirm': '1'})
        self.assertContains(response, 'sem mapeamento')
        self.assertTrue(person.escolhas.filter(pk=old.pk).exists())
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

    def test_starting_skill_and_tool_choices_are_visible_and_preserved(self):
        from .character_engine import derive
        from .models import TbPersonagemProficiencia

        self.setup_creation()
        self.ruleset = self._ready_ruleset(self.ruleset)
        person, pc = self._legacy_person()
        skill = person.escolhas.create(origem=self.classe.nome,
            tipo='pericia', slot=0, valor='percepcao')
        tool = person.escolhas.create(origem=self.classe.nome,
            tipo='ferramenta', slot=0, valor='kit-de-herbalismo')
        proficiency = TbPersonagemProficiencia.objects.create(
            id_personagem=person, tipo='ferramenta', nome='Kit de Herbalismo',
            origem=self.classe.nome)
        before = next(row for row in derive(person)['pericias']
                      if row['nome'] == 'Percepção')
        self.assertTrue(before['proficiente'])
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': self.ruleset.checksum,
            'expected_level': '1', 'ability': 'wis', 'confirm': '1'}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            preview = self.client.get(url)
            self.assertContains(preview, 'Perícias e ferramentas iniciais preservadas')
            self.assertContains(preview, 'kit-de-herbalismo')
            self.assertNotContains(preview, 'Estas escolhas impedem')
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual({row['id'] for row in profile.regularization[
            'preserved_starting_choices']}, {skill.pk, tool.pk})
        self.assertEqual(person.escolhas.filter(pk__in=[skill.pk, tool.pk]).count(), 2)
        self.assertEqual(TbPersonagemProficiencia.objects.filter(pk=proficiency.pk).count(), 1)
        after = next(row for row in derive(person, ruleset=self.ruleset)['pericias']
                     if row['nome'] == 'Percepção')
        self.assertTrue(after['proficiente'])
        self.assertFalse(after['expertise'])

    def test_combined_legacy_choices_transfer_once_without_losing_assets(self):
        from .hunter_choices import favored_state
        from .hunter_masteries import available_options, state as mastery_state

        self.setup_creation()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        target = compose_order_revision(self.ruleset, class_id=self.classe.pk,
                                        order_ids=orders)
        target = self._ready_ruleset(target)
        person, pc = self._legacy_person()
        person.nivel = pc.nivel = 6
        person.save(update_fields=['nivel'])
        pc.save(update_fields=['nivel'])
        acquired = TbMagia.objects.create(nome='Magia de aventura antiga',
            slug='magia-de-aventura-antiga', nivel=1)
        owned = TbPersonagemMagia.objects.create(id_personagem=person,
            id_magia=acquired, nome=acquired.nome, nivel=1, preparada=True,
            origem='Aventura')
        item = TbPersonagemItem.objects.create(id_personagem=person,
            nome='Troféu antigo', qtd=2, origem_tipo='legado')
        history = TbPersonagemAventura.objects.create(id_personagem=person,
            nome_aventura='Caçada antiga', qtd_aventuras=4)
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Segredos de Caçador', niveladquirido=2)
        TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Inimigo Favorito', niveladquirido=2)
        secret = resolve_content(target, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)['secrets'][0]
        style = TbOpcaojogo.objects.get(slug='test-hunter-style')
        old_style = person.escolhas.create(origem='Estilo de Luta',
            tipo='estilo_luta', slot=0, id_opcao=style, valor=style.slug)
        old_secret = person.escolhas.create(origem='Segredos de Caçador',
            tipo='segredo', slot=0, valor=secret['id'])
        first = person.escolhas.create(origem='Inimigo Favorito',
            tipo='tipo_criatura', slot=0, valor='Bestas')
        second = person.escolhas.create(origem='Inimigo Favorito',
            tipo='tipo_criatura', slot=1, valor='Dragões')
        skill = person.escolhas.create(origem=self.classe.nome,
            tipo='pericia', slot=0, valor='percepcao')
        mastery_values = []
        for option in available_options(person, target):
            if option['value'].split('|')[0] not in {
                    value.split('|')[0] for value in mastery_values}:
                mastery_values.append(option['value'])
            if len(mastery_values) == 3:
                break
        self.assertEqual(len(mastery_values), 3)
        old_masteries = [person.escolhas.create(
            origem='Maestria de Arma (%s)' % self.classe.nome,
            tipo='maestria', slot=slot, valor=value)
            for slot, value in enumerate(mastery_values)]
        old_ids = [old_style.pk, old_secret.pk, first.pk, second.pk]
        old_ids.extend(row.pk for row in old_masteries)
        self.client.force_login(self.user)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': target.checksum, 'expected_level': '6',
            'ability': 'wis', 'confirm': '1',
            'order': str(orders['ordem-da-alianca-selvagem']),
            'secret': [secret['id']], 'confirm_style_id': str(old_style.pk),
            'confirm_secret_id': [str(old_secret.pk)],
            'confirm_favored_id': [str(first.pk), str(second.pk)],
            'active_favored_id': [str(first.pk)],
            'confirm_mastery_id': [str(row.pk) for row in old_masteries]}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            preview = self.client.get(url, {'order': payload['order']})
            self.assertEqual(preview.status_code, 200)
            self.assertFalse(preview.context['comparison']['unresolved_class_choices'])
            applied = self.client.post(url, payload)
        self.assertEqual(applied.status_code, 302, applied.content[:500])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(profile.selected, [secret['id']])
        self.assertEqual(favored_state(profile)['selected'], ['bestas'])
        self.assertEqual(profile.regularization['deferred_favored'], ['dragoes'])
        self.assertEqual(mastery_state(profile)['selected'], mastery_values)
        self.assertFalse(person.escolhas.filter(pk__in=old_ids).exists())
        self.assertTrue(person.escolhas.filter(pk=skill.pk).exists())
        self.assertEqual(person.escolhas.filter(tipo='hunter-style').count(), 1)
        self.assertEqual(person.escolhas.filter(tipo='hunter-favored').count(), 1)
        self.assertEqual(person.escolhas.filter(tipo='hunter-mastery').count(), 3)
        person.refresh_from_db()
        owned.refresh_from_db()
        self.assertEqual((person.carteira_pc, person.aventuras, person.braseiros),
                         (2345, 4, 6))
        self.assertEqual((owned.id_magia_id, owned.preparada), (acquired.pk, True))
        self.assertEqual(person.inventario.get(pk=item.pk).qtd, 2)
        self.assertTrue(person.aventuras_ledger.filter(pk=history.pk).exists())
        self.assertEqual(self.client.get(reverse('hunter_sheet',
            args=[person.pk])).status_code, 200)
