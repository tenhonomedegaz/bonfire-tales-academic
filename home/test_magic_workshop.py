# -*- coding: utf-8 -*-
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from home.character_engine import magias_concedidas
from home.magic_workshop import (
    character_casters,
    character_spell_access_map,
    parse_priced_materials,
    scroll_offer,
    spell_accessible_to_character,
    spell_is_log_castable,
    signature_spell_rules,
    transcription_terms_for_character,
)
from home.models import (
    TbClasse,
    TbClassehabilidade,
    TbMagia,
    TbOpcaojogo,
    TbPersonagem,
    TbPersonagemClasse,
    TbPersonagemEscolha,
    TbPersonagemMagiaAssinatura,
    TbPersonagemTalento,
    TbSolicitacaoTranscricao,
    TbTalento,
)
from home.spell_access import (
    set_spell_class_access, spell_class_query, spell_class_slugs)
from home.spellcasting import character_spell_list_delta


class MagicWorkshopTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='oficina', password='x')
        self.classe = TbClasse.objects.create(nome='Arquivista', slug='arquivista')
        TbClassehabilidade.objects.create(
            id_classe=self.classe, nome='Conjuração', descricao='Grimório.',
            niveladquirido=1, tags_json=[
                'spellcasting{ability:int, slots{progression:full}, '
                'list:arquivista, mode:prepared, pool:spellbook, '
                'acquire{initial:6, level_up:2, transcribe{source:spell_scroll, '
                'cost_po:50*spell_level, time_hours:2*spell_level}}}'
            ])
        self.spell = TbMagia.objects.create(
            nome='Fogo de Teste', slug='fogo-de-teste', nivel=1,
            escola='Evocação', classes='', classes_slugs=[])
        self.mark = TbTalento.objects.create(
            nome='Marca de Teste', slug='marca-de-teste', descricao='Expande a lista.',
            tags_json=[
                'requires:spellcasting, '
                'modify:spellcasting{list}.add{spell:fogo_de_teste}'
            ])
        self.personagem = TbPersonagem.objects.create(
            dono=self.user, nome='Escriba', nivel=3, inteligencia=16,
            carteira_pc=10000)
        TbPersonagemClasse.objects.create(
            id_personagem=self.personagem, id_classe=self.classe,
            nivel=3, principal=True)
        TbPersonagemTalento.objects.create(
            id_personagem=self.personagem, id_talento=self.mark,
            nome=self.mark.nome)

    def test_componentes_e_preco_do_pergaminho(self):
        parsed = parse_priced_materials(
            'M (um diamante de 1.000 PO, consumido pela magia, e um '
            'recipiente de 2.000 PO, reutilizável)')
        self.assertEqual(parsed['consumed_cost_po'], Decimal('1000'))
        self.assertEqual(parsed['reusable_cost_po'], Decimal('2000'))

        self.spell.componentes = 'M (incenso de 10 PO, que a magia consome)'
        offer = scroll_offer(self.spell)
        self.assertEqual(offer['base_price_po'], Decimal('60'))
        self.assertEqual(offer['material_price_po'], Decimal('10'))
        self.assertEqual(offer['price_po'], Decimal('60'))

        self.spell.componentes = 'M (um diamante de 100 PO, consumido pela magia)'
        offer = scroll_offer(self.spell)
        self.assertEqual(offer['price_po'], Decimal('100'))
        self.assertTrue(offer['material_sets_price'])

    def test_acesso_base_usa_slugs_validados(self):
        set_spell_class_access(self.spell, [self.classe], save=True)
        self.spell.refresh_from_db()
        self.assertEqual(self.spell.classes_slugs, ['arquivista'])
        self.assertEqual(self.spell.classes, 'Arquivista')
        self.assertEqual(spell_class_slugs(self.spell), ['arquivista'])

        extended = TbClasse.objects.create(
            nome='Arquivista Maior', slug='arquivista-maior')
        other = TbMagia.objects.create(
            nome='Somente Maior', slug='somente-maior', nivel=1)
        set_spell_class_access(other, [extended], save=True)
        found = set(TbMagia.objects.filter(
            spell_class_query(['arquivista'])).values_list('slug', flat=True))
        self.assertEqual(found, {self.spell.slug})

    def test_editor_inline_rejeita_classe_inexistente_e_sincroniza_validas(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.user.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbmagia',
        ))
        self.client.force_login(self.user)
        url = reverse('wiki_update_spell', args=[self.spell.pk])
        payload = {
            'nome': self.spell.nome, 'slug': self.spell.slug,
            'nivel': self.spell.nivel, 'escola': self.spell.escola,
            'classes_slugs': ['nao-existe'], 'tags_json': [],
        }
        invalid = self.client.post(
            url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(invalid.status_code, 400)

        payload['classes_slugs'] = [self.classe.slug]
        valid = self.client.post(
            url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(valid.status_code, 200)
        self.spell.refresh_from_db()
        self.assertEqual(self.spell.classes_slugs, ['arquivista'])
        self.assertEqual(self.spell.classes, 'Arquivista')

    def test_marca_expande_lista_sem_conceder_magia(self):
        delta = character_spell_list_delta(self.personagem)
        self.assertEqual(delta['add'], {'fogo-de-teste'})
        self.assertEqual(delta['remove'], set())
        self.assertTrue(spell_accessible_to_character(
            self.personagem, self.spell,
            casters=character_casters(self.personagem)))
        granted = {row['slug'] for row in magias_concedidas(
            self.personagem)['concedidas']}
        self.assertNotIn(self.spell.slug, granted)

    def test_mapa_de_acesso_nao_repete_consultas_por_magia(self):
        extra = [TbMagia(
            nome='Magia %02d' % index, slug='magia-%02d' % index, nivel=1,
            classes=self.classe.nome, classes_slugs=[self.classe.slug])
            for index in range(30)]
        TbMagia.objects.bulk_create(extra)
        spells = list(TbMagia.objects.order_by('pk'))
        casters = character_casters(self.personagem)
        with CaptureQueriesContext(connection) as queries:
            access = character_spell_access_map(
                self.personagem, spells, casters=casters)
        self.assertLess(len(queries), 25)
        self.assertTrue(all(spell.pk in access for spell in extra))

    def test_conjuracao_da_oficina_exige_persistencia_declarada(self):
        transient = TbMagia.objects.create(
            nome='Clarão Breve', slug='clarao-breve', nivel=1,
            duracao='1 minuto')
        direct = TbMagia.objects.create(
            nome='Selo Duradouro', slug='selo-duradouro', nivel=1,
            duracao='Até ser dissipado')
        tagged = TbMagia.objects.create(
            nome='Vínculo Duradouro', slug='vinculo-duradouro', nivel=1,
            duracao='Instantâneo', tags_json=[
                'while_active{duration:indefinite, log_castable}'])
        self.assertFalse(spell_is_log_castable(transient))
        self.assertTrue(spell_is_log_castable(direct))
        self.assertTrue(spell_is_log_castable(tagged))
        owned = self.personagem.magias.create(
            id_magia=transient, nivel=1, nome=transient.nome,
            preparada=True, origem=self.classe.nome)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('oficina_conjurar_magia', args=[self.personagem.pk]),
            {'personagem': self.personagem.pk,
             'magia_personagem': owned.pk, 'slot': 1})
        self.assertIn('status=nao_persistente', response['Location'])
        self.assertFalse(self.personagem.transacoes.exists())

    def test_marca_nao_cria_conjuracao_em_nao_conjurador(self):
        martial = TbClasse.objects.create(nome='Marcial', slug='marcial')
        personagem = TbPersonagem.objects.create(
            dono=self.user, nome='Sem Magia', nivel=3)
        TbPersonagemClasse.objects.create(
            id_personagem=personagem, id_classe=martial,
            nivel=3, principal=True)
        TbPersonagemTalento.objects.create(
            id_personagem=personagem, id_talento=self.mark,
            nome=self.mark.nome)
        self.assertEqual(character_spell_list_delta(personagem)['add'], set())
        self.assertEqual(spell_accessible_to_character(
            personagem, self.spell), [])

    def test_marca_libera_compra_e_reembolso_de_pergaminho(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('oficina_comprar_pergaminho', args=[self.personagem.pk]),
            {'personagem': self.personagem.pk, 'magia': self.spell.slug})
        self.assertIn('status=comprado', response['Location'])
        self.personagem.refresh_from_db()
        self.assertEqual(self.personagem.carteira_pc, 4000)
        item = self.personagem.inventario.get(origem_tipo='oficina')
        self.assertIn('spell_scroll{spell:fogo_de_teste', item.tags_json[0])
        purchase = self.personagem.transacoes.get(tipo='compra')
        refund = self.client.post(reverse(
            'personagem_reembolsar_compra',
            args=[self.personagem.pk, purchase.pk]))
        self.assertIn('reembolso=ok', refund['Location'])
        self.personagem.refresh_from_db()
        self.assertEqual(self.personagem.carteira_pc, 10000)
        self.assertFalse(self.personagem.inventario.filter(pk=item.pk).exists())

    def test_pagina_da_oficina_renderiza_catalogo_efetivo(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('oficina_magia'), {'personagem': self.personagem.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pergaminho de Fogo de Teste')
        self.assertContains(response, 'Grimório')
        self.assertContains(response, f'href="{reverse("magias_listas")}?magia=fogo-de-teste"')
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'aria-controls="workshop-panel-scrolls"')

    def test_conjuracao_consumivel_e_preserva_foco(self):
        spell = TbMagia.objects.create(
            nome='Ritual de Teste', slug='ritual-de-teste', nivel=0,
            componentes=(
                'M (pó de prata de 10 PO, consumido pela magia, e um foco '
                'de cristal de 50 PO, reutilizável)'),
            classes='Arquivista', classes_slugs=['arquivista'],
            tags_json=['log_castable'])
        owned = self.personagem.magias.create(
            id_magia=spell, nivel=0, nome=spell.nome, preparada=True,
            origem=self.classe.nome)
        consumable = self.personagem.inventario.create(
            nome='Componentes consumíveis de Ritual de Teste', qtd=1,
            origem_tipo='oficina', tags_json=[
                'spell_component{spell:ritual_de_teste, kind:consumable, cost_po:10}',
                'consumable'])
        focus = self.personagem.inventario.create(
            nome='Componentes reutilizáveis de Ritual de Teste', qtd=1,
            origem_tipo='oficina', tags_json=[
                'spell_component{spell:ritual_de_teste, kind:focus, cost_po:50}'])
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('oficina_conjurar_magia', args=[self.personagem.pk]),
            {'personagem': self.personagem.pk,
             'magia_personagem': owned.pk})
        self.assertIn('status=conjurada', response['Location'])
        self.assertFalse(self.personagem.inventario.filter(
            pk=consumable.pk).exists())
        self.assertTrue(self.personagem.inventario.filter(
            pk=focus.pk, qtd=1).exists())
        movement = self.personagem.transacoes.get()
        self.assertEqual(
            movement.detalhes_json['operacao'], 'conjuracao_fora_combate')
        state = self.personagem.estados.get(ativo=True)
        self.assertEqual(state.origem, 'magia:ritual-de-teste')
        self.assertEqual(state.payload_json['spell_id'], spell.pk)
        response = self.client.post(
            reverse('oficina_encerrar_efeito', args=[self.personagem.pk]),
            {'personagem': self.personagem.pk, 'estado': state.chave,
             'tab': 'casting'})
        self.assertIn('status=estado_encerrado', response['Location'])
        state.refresh_from_db()
        self.assertFalse(state.ativo)
        self.assertTrue(movement.detalhes_json['componente_consumido'])

    def test_pergaminho_acima_do_teto_exige_teste_e_e_consumido_na_falha(self):
        self.spell.nivel = 3
        self.spell.save(update_fields=['nivel'])
        item = self.personagem.inventario.create(
            nome='Pergaminho de Fogo de Teste', qtd=1,
            origem_tipo='oficina', tags_json=[
                'spell_scroll{spell:fogo_de_teste, level:3, '
                'save_dc:15, attack_bonus:7}', 'consumable'])
        self.client.force_login(self.user)
        with mock.patch('secrets.randbelow', return_value=0):
            response = self.client.post(
                reverse('oficina_usar_pergaminho', args=[self.personagem.pk]),
                {'personagem': self.personagem.pk, 'item': item.pk})
        self.assertIn('status=pergaminho_usado', response['Location'])
        self.assertFalse(self.personagem.inventario.filter(pk=item.pk).exists())
        movement = self.personagem.transacoes.get()
        self.assertFalse(movement.detalhes_json['sucesso'])
        self.assertTrue(movement.detalhes_json['teste_exigido'])
        self.assertEqual(movement.detalhes_json['cd'], 13)
        self.assertEqual(movement.detalhes_json['scroll_save_dc'], 15)
        self.assertEqual(movement.detalhes_json['scroll_attack_bonus'], 7)

    def test_escola_de_foco_reduz_transcricao_sem_nome_de_subclasse(self):
        option = TbOpcaojogo.objects.create(
            nome='Evocação', slug='evocacao', tipo='Escola de Foco')
        TbPersonagemEscolha.objects.create(
            id_personagem=self.personagem, origem='Escolas de Foco',
            tipo='escola_de_foco', slot=0, id_opcao=option,
            valor=option.nome)
        caster = character_casters(self.personagem)[0]
        self.spell.nivel = 3
        terms = transcription_terms_for_character(
            self.personagem, caster, self.spell)
        self.assertEqual(terms['cost_po'], 75)
        self.assertEqual(terms['time_hours'], 3)
        self.assertTrue(terms['focus_discount'])

    def test_pedido_entre_grimorios_e_auditavel(self):
        set_spell_class_access(self.spell, [self.classe], save=True)
        source_user = User.objects.create_user(username='fonte', password='x')
        source = TbPersonagem.objects.create(
            dono=source_user, nome='Outro Grimório', nivel=3)
        TbPersonagemClasse.objects.create(
            id_personagem=source, id_classe=self.classe,
            nivel=3, principal=True)
        source.magias.create(
            id_magia=self.spell, nivel=1, nome=self.spell.nome,
            origem=self.classe.nome)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('oficina_solicitar_transcricao', args=[self.personagem.pk]),
            {'personagem': self.personagem.pk, 'fonte': source.pk,
             'magia': self.spell.pk, 'classe': self.classe.pk})
        self.assertIn('status=solicitado', response['Location'])
        request_row = TbSolicitacaoTranscricao.objects.get()
        self.assertEqual(request_row.status, 'pendente')

        self.client.force_login(source_user)
        response = self.client.post(
            reverse('oficina_responder_transcricao', args=[request_row.pk]),
            {'personagem': source.pk, 'acao': 'aceitar'})
        self.assertIn('status=aceita', response['Location'])
        request_row.refresh_from_db()
        self.personagem.refresh_from_db()
        self.assertEqual(request_row.status, 'aceita')
        self.assertEqual(self.personagem.carteira_pc, 5000)
        self.assertTrue(self.personagem.magias.filter(
            id_magia=self.spell, origem=self.classe.nome).exists())
        self.assertEqual(self.personagem.transacoes.count(), 1)
        self.assertEqual(source.transacoes.count(), 1)

    def test_centelha_referencia_escolhas_da_habilidade_base(self):
        from home.character_engine import (
            _grants_de_tag, _norm_escola, _resolve_pool)

        for name, slug in (
                ('Clérigo', 'clerigo'), ('Druida', 'druida'), ('Mago', 'mago')):
            TbClasse.objects.create(nome=name, slug=slug)
        eligible = TbMagia.objects.create(
            nome='Explosão Elegível', slug='explosao-elegivel', nivel=2,
            escola='Evocação', concentracao=False, classes='Mago')
        concentration = TbMagia.objects.create(
            nome='Explosão Concentrada', slug='explosao-concentrada', nivel=2,
            escola='Evocação', concentracao=True, classes='Mago')
        wrong_school = TbMagia.objects.create(
            nome='Ilusão Incorreta', slug='ilusao-incorreta', nivel=2,
            escola='Ilusão', concentracao=False, classes='Mago')
        spells = [eligible, concentration, wrong_school]
        catalog = {spell.slug: spell.nivel for spell in spells}
        rich = {
            spell.slug: (
                spell.nivel, _norm_escola(spell.escola), {spell.classes},
                bool(spell.concentracao))
            for spell in spells
        }
        tag = (
            'spell_selection:pick{lista:{clerigo | druida | mago}}'
            '{nivel:2, escola:ability{centelha_arcana, raca:humano}.escola, '
            'not{concentration}, qtd:1, '
            'spell_mod:ability{centelha_arcana, raca:humano}.spell_mod}')
        _fixed, choice, _reserved = _grants_de_tag(
            tag, {}, catalog, 5, casts_selection=True,
            feature_choices={
                'centelha_arcana': {'escola': 'evocacao', 'spell_mod': 'int'}})
        self.assertIsNotNone(choice)
        self.assertEqual(_resolve_pool(choice['pool'], rich), [eligible.slug])

    def test_bonus_de_pv_draconico_usa_nivel_da_classe(self):
        from home.character_engine import (
            _build_ctx, apply_tags, bonus_proficiencia)

        attrs = {
            sig: {'valor': 10, 'mod': 0}
            for sig in ('FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR')
        }
        feature = type('Feature', (), {
            'nome': 'Sangue da Estirpe', 'table_only': False,
            'tags_json': ['always_active{ buff:max_hp:+classlvl }'],
        })()
        state = {
            '_ctx': _build_ctx(10, bonus_proficiencia(10), attrs),
            'pv': {'maximo_calculado': 50}, 'velocidade': '9 m / 30 ft',
            'iniciativa': 0, 'recursos': {}, 'ca': 10,
        }
        apply_tags(
            state, [('subclasse', 'Feiticeiro', feature, 6)], escolhas={})
        self.assertEqual(state['pv']['maximo_calculado'], 56)

    def test_criador_de_assinatura_grava_nova_magia_no_grimorio(self):
        pc = self.personagem.classes.get(id_classe=self.classe)
        pc.nivel = 7
        pc.save(update_fields=['nivel'])
        self.personagem.nivel = 7
        self.personagem.save(update_fields=['nivel'])
        TbClassehabilidade.objects.create(
            id_classe=self.classe, nome='Magia Assinatura', descricao='Crie.',
            niveladquirido=7, tags_json=[
                'spellcraft{kind:signature_spell, slot:1, source:spellbook, '
                'school:focus, max_base_level:2, '
                'max_final_level:spell_slot_max, remodel_at{11,15}}'])
        focus = TbOpcaojogo.objects.create(
            nome='Evocação', slug='evocacao', tipo='Escola de Foco')
        TbPersonagemEscolha.objects.create(
            id_personagem=self.personagem, origem='Escolas de Foco',
            tipo='escola_de_foco', slot=0, id_opcao=focus,
            valor=focus.nome)
        self.spell.escola = 'Evocação'
        self.spell.casting_time = '1 Ação'
        self.spell.componentes = 'V, S'
        self.spell.save(update_fields=['escola', 'casting_time', 'componentes'])
        owned = self.personagem.magias.create(
            id_magia=self.spell, nivel=1, nome=self.spell.nome,
            origem=self.classe.nome)

        rules = signature_spell_rules(self.personagem)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['remodel_at'], [11, 15])
        self.assertEqual([row['owned'].pk for row in rules[0]['spells']], [owned.pk])

        self.client.force_login(self.user)
        page = self.client.get(
            reverse('oficina_magia'), {'personagem': self.personagem.pk})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Criador de Magia Assinatura')
        response = self.client.post(reverse(
            'oficina_salvar_magia_assinatura', args=[self.personagem.pk]), {
                'personagem': self.personagem.pk, 'classe': self.classe.pk,
                'slot': 1, 'magia_base': owned.pk,
                'nome': 'Fórmula Ígnea do Escriba', 'acao_bonus': '1',
                'remover_componente': ['V'], 'tab': 'signature',
            })
        self.assertIn('status=assinatura_ok', response['Location'])
        signature = TbPersonagemMagiaAssinatura.objects.get()
        self.assertEqual(signature.nivel_final, 3)
        self.assertEqual(signature.modificacoes_json['removed_components'], ['V'])
        self.assertEqual(signature.id_magia_personagem.nome, 'Fórmula Ígnea do Escriba')
        self.client.post(reverse(
            'personagem_toggle_magia', args=[
                self.personagem.pk, signature.id_magia_personagem_id]))
        signature.id_magia_personagem.refresh_from_db()
        owned.refresh_from_db()
        self.assertTrue(signature.id_magia_personagem.preparada)
        self.assertFalse(owned.preparada)
