# -*- coding: utf-8 -*-
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from home import views
from home.models import (
    TbClasse,
    TbClassehabilidade,
    TbMagia,
    TbPersonagem,
    TbPersonagemClasse,
    TbPersonagemItem,
    TbRecursoclasse,
)
from home.spellcasting import (
    class_spellcasting_contract,
    max_spell_level_at,
    spell_scroll_slug,
    transcription_terms,
)


class SpellcastingContractTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Arquivista', slug='arquivista')
        TbClassehabilidade.objects.create(
            id_classe=self.classe,
            nome='Conjuração Arquivista',
            descricao='Registra e prepara magias.',
            niveladquirido=1,
            tags_json=[
                'spellcasting{ability:int, slots{progression:full}, list:arquivista, '
                'mode:prepared, spell_limit{formula:classlvl+int_mod}, '
                'spell_level_limit{fixed:5}, '
                'pool:spellbook, acquire{initial:6, level_up:2, '
                'transcribe{source:spell_scroll, cost_po:50*spell_level, '
                'time_hours:2*spell_level}}, focus:spellbook}'
            ],
        )

    def test_parser_preserva_contrato_completo(self):
        contract = class_spellcasting_contract(self.classe, level=1)
        self.assertEqual(contract['mode'], 'prepared')
        self.assertEqual(contract['pool'], 'spellbook')
        self.assertEqual(contract['slots'], 'full')
        self.assertEqual(contract['spell_level_limit'], {'kind': 'fixed', 'value': '5'})
        self.assertEqual(contract['acquire']['initial'], 6)
        self.assertEqual(contract['acquire']['level_up'], 2)
        self.assertEqual(contract['acquire']['transcribe']['source'], 'spell_scroll')
        self.assertEqual(
            transcription_terms(contract, spell_level=3),
            {'cost_po': 150, 'time_hours': 6, 'source': 'spell_scroll'},
        )

    def test_pergaminho_e_identificado_pela_tag_e_nao_pelo_nome(self):
        self.assertEqual(
            spell_scroll_slug(['spell_scroll{spell:raio-de-teste}']),
            'raio-de-teste',
        )
        self.assertIsNone(spell_scroll_slug(['consumable', 'slot:pergaminho']))


class SpellcastingCharacterEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pact-engine', password='x')
        self.classe = TbClasse.objects.create(nome='Pactário', slug='pactario')
        TbClassehabilidade.objects.create(
            id_classe=self.classe,
            nome='Conjuração por Ciclos',
            descricao='Conjura por um recurso próprio.',
            niveladquirido=1,
            tags_json=[
                'spellcasting{ability:cha, slots{progression:pact, '
                'resource:pontos_de_pacto}, list:pactario, mode:known, '
                'spell_level_limit{resource:ciclo_de_magia}}'
            ],
        )
        TbRecursoclasse.objects.create(
            id_classe=self.classe, nome='Ciclo de Magia',
            slug='ciclo_de_magia', nivel=1, valor='1',
            valores_json={'1': '1', '3': '2'}, tipo='table-only')
        self.personagem = TbPersonagem.objects.create(
            dono=self.user, nome='Pactário de Teste', nivel=3, carisma=16)
        TbPersonagemClasse.objects.create(
            id_personagem=self.personagem, id_classe=self.classe,
            nivel=3, principal=True)

    def test_motor_reconhece_sintaxe_canonica_e_teto_por_recurso(self):
        from home.character_engine import _conjuracao_real, _teto_nivel_conjuravel

        contract = class_spellcasting_contract(self.classe, level=3)
        self.assertTrue(_conjuracao_real(self.personagem))
        self.assertEqual(
            max_spell_level_at(contract, self.classe, level=3), 2)
        self.assertEqual(_teto_nivel_conjuravel(self.personagem), 2)


class SpellTranscriptionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='scribe', password='x')
        self.classe = TbClasse.objects.create(nome='Arquivista', slug='arquivista')
        TbClassehabilidade.objects.create(
            id_classe=self.classe,
            nome='Conjuração Arquivista',
            descricao='Registra e prepara magias.',
            niveladquirido=1,
            tags_json=[
                'spellcasting{ability:int, slots{progression:full}, list:arquivista, '
                'mode:prepared, spell_limit{formula:classlvl+int_mod}, '
                'pool:spellbook, acquire{initial:6, level_up:2, '
                'transcribe{source:spell_scroll, cost_po:50*spell_level, '
                'time_hours:2*spell_level}}, focus:spellbook}'
            ],
        )
        TbRecursoclasse.objects.create(
            id_classe=self.classe, nome='1º', slug='1o', nivel=1,
            valor='2', valores_json={'1': '2'}, tipo='table-only')
        self.spell = TbMagia.objects.create(
            nome='Raio de Teste', slug='raio-de-teste', nivel=1,
            classes='Arquivista')
        self.personagem = TbPersonagem.objects.create(
            dono=self.user, nome='Escriba', nivel=1, inteligencia=16,
            carteira_pc=5000)
        TbPersonagemClasse.objects.create(
            id_personagem=self.personagem, id_classe=self.classe,
            nivel=1, principal=True)
        self.item = TbPersonagemItem.objects.create(
            id_personagem=self.personagem, nome='Objeto sem nome mecânico', qtd=1,
            tags_json=['spell_scroll{spell:raio-de-teste}', 'consumable'])
        self.client.force_login(self.user)

    def test_transcricao_consumo_custo_e_grimorio(self):
        with mock.patch('secrets.randbelow', return_value=19):
            response = self.client.post(
                reverse('personagem_transcrever_magia', args=[self.personagem.pk]),
                {'classe': self.classe.pk, 'item': self.item.pk},
            )
        self.assertRedirects(
            response,
            reverse('ficha_detail', args=[self.personagem.pk]) +
            '?aba=magias&transcricao=ok',
            fetch_redirect_response=False,
        )
        self.personagem.refresh_from_db()
        self.assertEqual(self.personagem.carteira_pc, 0)
        self.assertFalse(TbPersonagemItem.objects.filter(pk=self.item.pk).exists())
        learned = self.personagem.magias.get(id_magia=self.spell, origem='Arquivista')
        self.assertFalse(learned.preparada)
        movement = self.personagem.transacoes.get()
        self.assertEqual(movement.valor_pc, -5000)
        self.assertEqual(movement.detalhes_json['operacao'], 'transcricao_magia')
        self.assertTrue(movement.detalhes_json['sucesso'])

    def test_falha_consume_custo_e_pergaminho_sem_aprender(self):
        with mock.patch('secrets.randbelow', return_value=0):
            response = self.client.post(
                reverse('personagem_transcrever_magia', args=[self.personagem.pk]),
                {'classe': self.classe.pk, 'item': self.item.pk},
            )
        self.assertIn('transcricao=falha', response['Location'])
        self.personagem.refresh_from_db()
        self.assertEqual(self.personagem.carteira_pc, 0)
        self.assertFalse(TbPersonagemItem.objects.filter(pk=self.item.pk).exists())
        self.assertFalse(self.personagem.magias.exists())
        movement = self.personagem.transacoes.get()
        self.assertFalse(movement.detalhes_json['sucesso'])
        self.assertEqual(movement.detalhes_json['cd'], 11)

    def test_saldo_insuficiente_nao_consume_item(self):
        self.personagem.carteira_pc = 4999
        self.personagem.save(update_fields=['carteira_pc'])
        response = self.client.post(
            reverse('personagem_transcrever_magia', args=[self.personagem.pk]),
            {'classe': self.classe.pk, 'item': self.item.pk},
        )
        self.assertIn('transcricao=saldo', response['Location'])
        self.assertTrue(TbPersonagemItem.objects.filter(pk=self.item.pk, qtd=1).exists())
        self.assertFalse(self.personagem.magias.exists())
