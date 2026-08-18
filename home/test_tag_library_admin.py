import copy
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import TbTagLibraryRevision, TbTalento
from home.tag_engine import Library, evaluate_tags
from home.tag_engine.governance import library_checksum
from home.tag_engine.library import clear_library_cache


class TagLibraryRuntimeTests(TestCase):
    def tearDown(self):
        clear_library_cache()

    def test_motor_le_revisao_ativa_do_banco_sem_novo_codigo(self):
        raw = copy.deepcopy(Library(prefer_db=False).raw)
        raw['primitives']['teste_dinamico'] = {
            'categoria': 'QA',
            'forma': 'key_value',
            'op': 'set_value',
            'target': 'qa.resultado',
            'doc': 'Primitiva criada exclusivamente para provar o dispatch dinâmico.',
        }
        TbTagLibraryRevision.objects.create(
            nome='QA dinâmico', motivo='Teste automatizado',
            conteudo_json=raw, checksum=library_checksum(raw), ativa=True,
            ativada_em=timezone.now(),
        )
        clear_library_cache()

        library = Library()
        result = evaluate_tags(['teste_dinamico:7'], library=library)

        self.assertEqual(library.source, 'database')
        self.assertEqual(result.state['qa']['resultado'], 7)
        self.assertEqual(result.operations[0].verb, 'teste_dinamico')


class TagLibraryAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin-tags', email='admin@example.com', password='senha-forte')
        self.client.force_login(self.user)
        self.url = reverse('admin:tag_library')

    def tearDown(self):
        clear_library_cache()

    def test_pagina_e_consulta_para_superuser(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Biblioteca de Tags')
        self.assertContains(response, 'Operações disponíveis no motor')
        self.assertContains(response, 'always_active')

    def test_editor_ativa_json_valido_e_motor_passa_a_le_lo(self):
        raw = copy.deepcopy(Library(prefer_db=False).raw)
        raw['primitives']['bonus_teste_admin'] = {
            'categoria': 'QA', 'forma': 'key_value',
            'op': 'add_modifier', 'target': 'qa.bonus',
            'doc': 'Verbo genérico criado pelo painel.',
        }

        response = self.client.post(self.url, {
            'action': 'activate_json',
            'library_json': json.dumps(raw, ensure_ascii=False),
            'revision_name': 'Nova primitiva pelo painel',
            'reason': 'Validar edição sem deploy',
        })

        self.assertEqual(response.status_code, 302)
        revision = TbTagLibraryRevision.objects.get(ativa=True)
        self.assertEqual(revision.criada_por, self.user)
        clear_library_cache()
        self.assertIn('bonus_teste_admin', Library().primitives)

    def test_editor_recusa_regressao_nas_tags_existentes(self):
        TbTalento.objects.create(
            nome='Talento protegido', slug='talento-protegido',
            descricao='Teste', tags_json=['resist:fogo'],
        )
        raw = copy.deepcopy(Library(prefer_db=False).raw)
        raw['primitives'].pop('resist')

        response = self.client.post(self.url, {
            'action': 'activate_json',
            'library_json': json.dumps(raw, ensure_ascii=False),
            'revision_name': 'Remoção perigosa',
            'reason': 'Tentar remover verbo utilizado',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TbTagLibraryRevision.objects.filter(ativa=True).exists())
        self.assertContains(response, 'Validação recusada')
        self.assertContains(response, 'Novos erros')

    def test_editor_recusa_operacao_inexistente(self):
        raw = copy.deepcopy(Library(prefer_db=False).raw)
        raw['primitives']['verbo_invalido'] = {
            'categoria': 'QA', 'forma': 'flag',
            'op': 'operacao_que_nao_existe',
            'doc': 'Não pode ser ativada.',
        }

        response = self.client.post(self.url, {
            'action': 'activate_json',
            'library_json': json.dumps(raw, ensure_ascii=False),
            'revision_name': 'Operação inválida',
            'reason': 'Garantir bloqueio do lint',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TbTagLibraryRevision.objects.filter(ativa=True).exists())
        self.assertTrue(any(
            "op 'operacao_que_nao_existe' não existe" in item['message']
            for item in response.context['report']['lint']
        ))
