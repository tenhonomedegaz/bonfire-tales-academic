from django.test import TestCase
from django.urls import reverse

from .models import TbBestiario
from .management.commands.importar_bestiario_csv import _descricao_markdown
from .management.commands.limpar_residuos_banco import _clean_creature_text


class BestiaryDescriptionProjectionTests(TestCase):
    def setUp(self):
        self.statblock = {
            'name': 'Sentinela', 'type': 'Construto', 'size': 'M',
            'alignment': 'neutro', 'cr': '2', 'ac_text': '14', 'hp': '30',
            'speed': '9 m', 'actions': [{'name': 'Golpe', 'entries': ['Causa dano.']}],
        }
        self.generated = _descricao_markdown({}, self.statblock)

    def test_exact_import_summary_is_not_duplicated_in_catalog_or_preview(self):
        creature = TbBestiario.objects.create(
            slug='sentinela-gerada', nome='Sentinela', tipo='Construto', nd='2',
            statblock_json=self.statblock,
            descricao_markdown=_clean_creature_text(self.generated), comunidade=False,
        )
        catalog = self.client.get(reverse('bestiario'))
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.context['criaturas'][0]['descricao'], '')
        self.assertIn('Golpe', catalog.content.decode())
        preview = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['descricao'], '')
        self.assertIn('Golpe', preview.json()['statblock_html'])
        creature.refresh_from_db()
        self.assertEqual(creature.descricao_markdown, _clean_creature_text(self.generated))

    def test_editorial_and_stale_summaries_remain_visible(self):
        for slug, description, community in (
            ('sentinela-editorial', 'História escrita pela mesa.', False),
            ('sentinela-stale', self.generated + '\n\nNota editorial.', False),
            ('sentinela-comunidade', self.generated, True),
        ):
            TbBestiario.objects.create(
                slug=slug, nome=slug, tipo='Construto', nd='2',
                statblock_json=self.statblock, descricao_markdown=description,
                comunidade=community,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()['descricao'], description.strip())
