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

    def test_import_summary_with_original_feature_name_uses_current_statblock(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Golpe de Vento', 'name_en': 'Wind Strike',
            'entries': ['Causa dano.'],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        stale = generated.replace('**Golpe de Vento**', '**Wind Strike**')
        creature = TbBestiario.objects.create(
            slug='sentinela-traduzida', nome='Sentinela', tipo='Construto',
            statblock_json=statblock, descricao_markdown=stale,
        )
        preview = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['descricao'], '')
        self.assertIn('Golpe de Vento', preview.json()['statblock_html'])
        creature.refresh_from_db()
        self.assertEqual(creature.descricao_markdown, stale)

    def test_extra_rule_or_changed_metadata_remains_for_review(self):
        generated = _clean_creature_text(self.generated)
        variants = (
            generated.replace('**Golpe**', '**Regra ausente**'),
            generated.replace('**Golpe**', '**Golpe**\n- **Regra adicional**'),
            generated.replace('**CA:** 14', '**CA:** 18'),
        )
        for index, description in enumerate(variants):
            creature = TbBestiario.objects.create(
                slug=f'sentinela-divergente-{index}', nome='Sentinela',
                statblock_json=self.statblock, descricao_markdown=description,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()['descricao'], description)

    def test_different_ability_qualifier_is_not_hidden(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Golpe (somente Slaad)',
            'name_en': 'Strike (Slaad Only)',
            'entries': ['Causa dano.'],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        altered = generated.replace('Golpe (somente Slaad)', 'Golpe (somente Beholderkin)')
        creature = TbBestiario.objects.create(
            slug='sentinela-qualificador', nome='Sentinela',
            statblock_json=statblock, descricao_markdown=altered,
        )
        response = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(response.json()['descricao'], altered)

    def test_stale_spell_mention_without_structured_reference_stays_visible(self):
        generated = _clean_creature_text(self.generated)
        stale = generated.replace('**Golpe**', '**Golpe** (Sleep)')
        creature = TbBestiario.objects.create(
            slug='sentinela-mencao-antiga', nome='Sentinela',
            statblock_json=self.statblock, descricao_markdown=stale,
        )
        response = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(response.json()['descricao'], stale)
        self.assertIn('Golpe', response.json()['statblock_html'])
        catalog = self.client.get(reverse('bestiario'), {'q': 'Sentinela'})
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.context['criaturas'][0]['descricao'], stale)

    def test_translated_spell_reference_must_match_structured_identity(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Golpe de Vento', 'name_en': 'Wind Strike',
            'entries': ['Causa dano.'],
            'spell_refs': [{'name': 'Rajada de Vento', 'name_en': 'Gust of Wind',
                            'slug': 'rajada-de-vento'}],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('**Golpe de Vento** (Rajada de Vento)',
                                '**Wind Strike** (Gust of Wind)')
        altered = old.replace('Gust of Wind', 'Fireball')
        for slug, description, visible in (
            ('sentinela-referencia-alinhada', old, False),
            ('sentinela-referencia-divergente', altered, True),
        ):
            creature = TbBestiario.objects.create(
                slug=slug, nome='Sentinela', statblock_json=statblock,
                descricao_markdown=description,
            )
            response = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
            self.assertEqual(bool(response.json()['descricao']), visible)
