from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbItemMagico, TbItemMundano


class ItemEditorIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_superuser(
            'item-integrity-editor', 'item-integrity@example.invalid', 'test-only',
        )
        cls.mundane = TbItemMundano.objects.create(
            nome='Corda editorial', slug='corda-editorial-integrity',
            categoria='equipamento_aventura', peso=1.5, preco='2 PO',
            descricao_markdown='Texto original', tags_json=['tool:rope'],
        )
        cls.magic = TbItemMagico.objects.create(
            nome='Anel editorial', slug='anel-editorial-integrity',
            raridade='incomum', slot='aneis', preco=Decimal('3.50'),
            descricao_markdown='Texto original', tags_json=['attunement'],
        )

    def setUp(self):
        self.client.force_login(self.editor)

    def mundane_form(self, **overrides):
        return {
            'nome': self.mundane.nome, 'slug': self.mundane.slug,
            'categoria': self.mundane.categoria, 'subcategoria': '',
            'peso': '1.5', 'preco': '2 PO', 'imagem_url': '',
            'descricao_markdown': 'Texto original', 'tags_json': 'tool:rope',
            **overrides,
        }

    def magic_form(self, **overrides):
        return {
            'nome': self.magic.nome, 'nome_ingles': '', 'slug': self.magic.slug,
            'raridade': self.magic.raridade, 'slot': self.magic.slot,
            'requer_sintonizacao': '', 'detalhes_sintonizacao': '',
            'loja': '', 'preco': '3.50', 'tipo': '', 'imagem_url': '',
            'descricao_markdown': 'Texto original', 'tags_json': 'attunement',
            **overrides,
        }

    def logs_for(self, item):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(item),
            object_id=str(item.pk), action_flag=CHANGE,
        )

    def test_invalid_numbers_preserve_both_public_items_and_history(self):
        mundane_url = reverse('wiki_update_mundane_item', args=[self.mundane.pk])
        magic_url = reverse('wiki_update_magic_item', args=[self.magic.pk])
        for peso in ('NaN', 'Infinity', '-1'):
            with self.subTest(peso=peso):
                self.assertEqual(self.client.post(mundane_url, self.mundane_form(
                    peso=peso, nome='Nome indevido',
                )).status_code, 400)
        for preco in ('NaN', 'Infinity', '-1', '1.234', '10000000000'):
            with self.subTest(preco=preco):
                self.assertEqual(self.client.post(magic_url, self.magic_form(
                    preco=preco, nome='Nome indevido',
                )).status_code, 400)
        self.mundane.refresh_from_db()
        self.magic.refresh_from_db()
        self.assertEqual(self.mundane.nome, 'Corda editorial')
        self.assertEqual(self.mundane.peso, 1.5)
        self.assertEqual(self.magic.nome, 'Anel editorial')
        self.assertEqual(self.magic.preco, Decimal('3.50'))
        self.assertFalse(self.logs_for(self.mundane).exists())
        self.assertFalse(self.logs_for(self.magic).exists())

    def test_identical_submit_skips_write_and_real_edit_is_audited(self):
        for item, url_name, form, label in (
            (self.mundane, 'wiki_update_mundane_item', self.mundane_form, 'Corda revisada'),
            (self.magic, 'wiki_update_magic_item', self.magic_form, 'Anel revisado'),
        ):
            with self.subTest(model=type(item).__name__):
                url = reverse(url_name, args=[item.pk])
                with patch.object(type(item), 'save', side_effect=AssertionError('identical item was saved')):
                    self.assertEqual(self.client.post(url, form()).status_code, 302)
                self.assertEqual(self.logs_for(item).count(), 0)
                self.assertEqual(self.client.post(url, form(nome=label)).status_code, 302)
                item.refresh_from_db()
                self.assertEqual(item.nome, label)
                self.assertEqual(list(self.logs_for(item).values_list('user_id', flat=True)), [self.editor.pk])
                with patch.object(type(item), 'save', side_effect=AssertionError('repeated item was saved')):
                    self.assertEqual(self.client.post(url, form(nome=label)).status_code, 302)
                self.assertEqual(self.logs_for(item).count(), 1)

    def test_audit_failure_rolls_back_item_change(self):
        url = reverse('wiki_update_magic_item', args=[self.magic.pk])
        with patch('django.contrib.admin.models.LogEntry.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(url, self.magic_form(nome='Nome não publicado'))
        self.magic.refresh_from_db()
        self.assertEqual(self.magic.nome, 'Anel editorial')
