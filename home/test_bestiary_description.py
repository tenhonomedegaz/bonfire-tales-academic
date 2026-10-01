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

    def test_accentless_legacy_label_matches_only_the_same_ability(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Resistência Lendária (3/dia)',
            'name_en': 'Legendary Resistance (3/Day)',
            'entries': ['Resiste a uma falha.'],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('Resistência Lendária (3/dia)', 'Resistencia Lendaria')
        different = generated.replace('Resistência Lendária (3/dia)',
                                      'Resistencia Lendaria (4/dia)')
        for slug, description, visible in (
            ('sentinela-label-sem-acento', old, False),
            ('sentinela-label-regra-diferente', different, True),
        ):
            creature = TbBestiario.objects.create(
                slug=slug, nome='Sentinela', statblock_json=statblock,
                descricao_markdown=description,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
            self.assertEqual(bool(preview.json()['descricao']), visible)

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

    def test_spell_reference_accents_match_but_other_spells_remain_visible(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Conjuracao', 'name_en': 'Spellcasting',
            'entries': ['Conjura uma magia.'],
            'spell_refs': [{'name': 'Visão Arcana', 'name_en': 'Arcane Sight',
                            'slug': 'visao-arcana'}],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('(Visão Arcana)', '(Visao Arcana)')
        for slug, description, visible in (
            ('sentinela-acento', old, False),
            ('sentinela-outra-magia', old.replace('Visao Arcana', 'Bola de Fogo'), True),
        ):
            creature = TbBestiario.objects.create(
                slug=slug, nome='Sentinela', statblock_json=statblock,
                descricao_markdown=description,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(bool(preview.json()['descricao']), visible)
            self.assertIn('Conjuracao', preview.json()['statblock_html'])

    def test_source_backed_sleep_prose_does_not_duplicate_statblock(self):
        trait = {
            'name': 'Natureza Incomum', 'name_en': 'Unusual Nature',
            'entries_en': ["The creature doesn't require air, food, drink, or sleep."],
            'entries': ['A criatura não precisa respirar, comer, beber ou dormir.'],
        }
        statblock = {**self.statblock, 'traits': [trait]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('**Natureza Incomum**', '**Natureza Incomum** (Sleep)')
        variants = (
            ('natureza-sono', statblock, old, False),
            ('natureza-outra-magia', statblock, old.replace('(Sleep)', '(Sleep, Fireball)'), True),
            ('natureza-conjura-sono', {**statblock, 'traits': [{**trait,
                'entries_en': ['The creature casts Sleep and does not need to sleep.']}]},
             old, True),
            ('natureza-tag-ativa', {**statblock, 'traits': [{**trait,
                'tags_json': ['cast{spell:sono}']}]}, old, True),
        )
        for slug, current_statblock, description, visible in variants:
            creature = TbBestiario.objects.create(
                slug=slug, nome='Sentinela', statblock_json=current_statblock,
                descricao_markdown=description,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(bool(preview.json()['descricao']), visible)
            self.assertIn('Natureza Incomum', preview.json()['statblock_html'])
        catalog = self.client.get(reverse('bestiario'), {'q': 'natureza-sono'})
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.context['criaturas'][0]['descricao'], '')

    def test_devils_sight_requires_both_old_prose_labels(self):
        trait = {
            'name': 'Visão do Diabo', 'name_en': "Devil's Sight",
            'entries_en': ["Magical darkness doesn't impede the creature's darkvision."],
            'entries': ['Escuridão mágica não impede sua visão no escuro.'],
        }
        statblock = {**self.statblock, 'traits': [trait]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        for slug, labels, visible in (
            ('visao-do-diabo-antiga', 'Darkness, Darkvision', False),
            ('visao-do-diabo-incompleta', 'Darkness', True),
        ):
            description = generated.replace('**Visão do Diabo**',
                                            f'**Visão do Diabo** ({labels})')
            TbBestiario.objects.create(slug=slug, nome='Sentinela',
                                       statblock_json=statblock,
                                       descricao_markdown=description)
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(bool(preview.json()['descricao']), visible)

    def test_parser_prose_heading_is_hidden_only_when_full_summary_matches(self):
        sentence = 'The creature can hold only one swallowed target at a time.'
        statblock = {**self.statblock, 'actions': [{
            'name': 'Engolir', 'name_en': 'Swallow',
            'entries_en': [f'The creature bites its target. {sentence}'],
            'entries': ['A criatura morde o alvo e pode engolir apenas um alvo.'],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('- **Engolir**',
                                f'- **Engolir**\n- **{sentence}**')
        variants = (
            ('engolir-prosa-antiga', old, False),
            ('engolir-regra-extra', old + '\n- **Regra editorial nova**', True),
            ('engolir-ca-alterada', old.replace('**CA:** 14', '**CA:** 18'), True),
        )
        for slug, description, visible in variants:
            creature = TbBestiario.objects.create(
                slug=slug, nome='Sentinela', statblock_json=statblock,
                descricao_markdown=description,
            )
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(bool(preview.json()['descricao']), visible)
            self.assertIn('Engolir', preview.json()['statblock_html'])
            creature.refresh_from_db()
            self.assertEqual(creature.descricao_markdown, description)
        catalog = self.client.get(reverse('bestiario'), {'q': 'engolir-prosa-antiga'})
        self.assertEqual(catalog.context['criaturas'][0]['descricao'], '')

    def test_dim_light_and_darkness_are_not_old_spell_references(self):
        action = {
            'name': 'Salto Sombrio', 'name_en': 'Shadow Jump',
            'entries_en': ['The creature moves between spaces of dim light or darkness.'],
            'entries': ['A criatura se move entre espaços de penumbra ou escuridão.'],
        }
        statblock = {**self.statblock, 'actions': [action]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        old = generated.replace('**Salto Sombrio**',
                                '**Salto Sombrio** (Light, Darkness)')
        variants = (
            ('salto-ambiental', statblock, old, False),
            ('salto-conjura', {**statblock, 'actions': [{**action,
                'entries_en': ['The creature casts Darkness in dim light or darkness.']}]},
             old, True),
            ('salto-tag', {**statblock, 'actions': [{**action,
                'tags': ['cast{spell:escuridao}']}]}, old, True),
            ('salto-outra-regra', statblock, old + '\n- **Regra adicional**', True),
        )
        for slug, current_statblock, description, visible in variants:
            TbBestiario.objects.create(slug=slug, nome='Sentinela',
                                       statblock_json=current_statblock,
                                       descricao_markdown=description)
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(bool(preview.json()['descricao']), visible)
            self.assertIn('Salto Sombrio', preview.json()['statblock_html'])
        catalog = self.client.get(reverse('bestiario'), {'q': 'salto-ambiental'})
        self.assertEqual(catalog.context['criaturas'][0]['descricao'], '')

    def test_partially_translated_old_feature_label_keeps_rule_qualifier_guard(self):
        statblock = {**self.statblock, 'actions': [{
            'name': 'Esmagamento Psíquico (Recarga 5–6)',
            'name_en': 'Psychic Crush (Recharge 5–6)',
            'entries': ['Causa dano psíquico.'],
        }]}
        generated = _clean_creature_text(_descricao_markdown({}, statblock))
        for slug, label, visible in (
            ('rotulo-antigo-misto', 'psíquico Crush', False),
            ('rotulo-regra-divergente', 'psíquico Crush (Recharge 4–6)', True),
        ):
            description = generated.replace('Esmagamento Psíquico (Recarga 5–6)', label)
            TbBestiario.objects.create(slug=slug, nome='Sentinela',
                                       statblock_json=statblock,
                                       descricao_markdown=description)
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(bool(preview.json()['descricao']), visible)
