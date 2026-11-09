"""Published mechanics must not depend on which class starts a sandbox build."""
from django.test import override_settings
from django.urls import reverse

from . import test_hunter_legacy_migration as migration
from .class_revision_editor import create_class_revision
from .models import TbClassPublication, TbPersonagem, TbPersonagemCacador
from .pathbuilder import PathbuilderError, _apply_classes, catalogos
from .pathbuilder import simulate_build
from .test_criador import _CriadorBase


class PathbuilderRevisionTests(_CriadorBase):
    setup_catalog = migration.HunterLegacyMigrationTests.setup_catalog
    setUp = migration.HunterLegacyMigrationTests.setUp
    _assets = migration.HunterLegacyMigrationTests._assets

    def build(self, **hunter):
        return {'modo': 'sandbox', 'classes': [
            {'slug': 'guerreiro', 'nivel': 2},
            {'slug': 'cacador', 'nivel': 5, 'subclasse': 'ordem-dos-mutantes-rework', **hunter}],
            'atributos_bonus': {}, 'escolhas': {}, 'talentos': [], 'itens': [], 'magias': []}

    def test_preparation_uses_pinned_secrets_automatic_line_and_total_proficiency(self):
        from unittest.mock import patch
        from .content_versions import resolve_content
        from .versioned_classes import EVALUATOR, VOCABULARY
        data = resolve_content(self.target, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        line = next(o['line'] for o in data['orders'] if o['id'] == 'ordem-dos-mutantes')
        selected = [r['id'] for r in data['secrets'] if r['level'] <= 5 and r['line'] != line][:3]
        build = self.build(ability='int')
        build['escolhas']['preparation|cacador|secrets'] = selected
        before = (TbPersonagem.objects.count(), TbPersonagemCacador.objects.count(), self._assets())
        with patch('home.hunter_rework.catalog', side_effect=AssertionError('live fallback')):
            result = simulate_build(self.user, self._payload('guerreiro'), build)
        group = next(g for g in result['escolhas_grupos'] if g['kind'] == 'preparation')
        automatic = [r for r in data['secrets'] if r['level'] <= 5 and r['line'] == line]
        exclusive = [r for r in data.get('exclusive_secrets', [])
                     if r['level'] <= 5 and r['order'] == 'ordem-dos-mutantes']
        self.assertEqual(group['selecionadas'], selected)
        self.assertEqual(group['limite'] - len(group['automaticas']), 3)
        self.assertEqual(len(group['automaticas']), len(automatic) + len(exclusive))
        self.assertEqual(group['opcionais_restantes'], 0)
        self.assertFalse(group['pendentes'])
        self.assertTrue(all(o['valor'] not in {r['id'] for r in automatic} for o in group['opcoes']))
        self.assertTrue(all(o['valor'] in {r['id'] for r in data['secrets'] if r['level'] <= 5}
                            for o in group['opcoes']))
        self.assertEqual(before, (TbPersonagem.objects.count(), TbPersonagemCacador.objects.count(), self._assets()))

    def test_preparation_rejects_locked_automatic_duplicate_and_over_limit(self):
        from .hunter_rework import catalog
        data = catalog()
        line = next(o['line'] for o in data['orders'] if o['id'] == 'ordem-dos-mutantes')
        optional = [r['id'] for r in data['secrets'] if r['level'] <= 5 and r['line'] != line]
        automatic = next(r['id'] for r in data['secrets'] if r['level'] <= 5 and r['line'] == line)
        locked = next(r['id'] for r in data['secrets'] if r['level'] > 5)
        before = (TbPersonagem.objects.count(), TbPersonagemCacador.objects.count())
        for selected in ([locked], [automatic], ['not-a-secret'], optional[:4], [optional[0]] * 2):
            with self.subTest(selected=selected):
                build = self.build(ability='wis')
                build['escolhas']['preparation|cacador|secrets'] = selected
                with self.assertRaises(PathbuilderError):
                    simulate_build(self.user, self._payload('guerreiro'), build)
                self.assertEqual(before, (TbPersonagem.objects.count(), TbPersonagemCacador.objects.count()))

    def test_preparation_level_two_and_removal_are_recomputed_without_persistence(self):
        build = self.build(ability='int', nivel=2, subclasse='')
        first = simulate_build(self.user, self._payload('guerreiro'), build)
        group = next(g for g in first['escolhas_grupos'] if g['kind'] == 'preparation')
        self.assertFalse(group['automaticas'])
        key = group['key']
        build['escolhas'][key] = [group['opcoes'][0]['valor']]
        chosen = simulate_build(self.user, self._payload('guerreiro'), build)
        self.assertEqual(next(g for g in chosen['escolhas_grupos'] if g['key'] == key)['usados'], 1)
        build['escolhas'][key] = []
        cleared = simulate_build(self.user, self._payload('guerreiro'), build)
        self.assertEqual(next(g for g in cleared['escolhas_grupos'] if g['key'] == key)['usados'], 0)
        build['classes'][1]['nivel'] = 1
        hidden = simulate_build(self.user, self._payload('guerreiro'), build)
        self.assertFalse(any(g['kind'] == 'preparation' for g in hidden['escolhas_grupos']))

    def test_lunareth_hunter_can_choose_tag_granted_perception_in_laboratory(self):
        from .character_engine import derive
        from .models import TbLinhagem, TbRaca
        from .pathbuilder_preparations import apply_expertise_choices, expertise_groups
        self.person.id_raca = TbRaca.objects.get(slug='elfo')
        self.person.id_linhagem = TbLinhagem.objects.get(slug='lunareth')
        self.person.save(update_fields=['id_raca', 'id_linhagem'])
        build = {'classes': [{'slug': 'cacador', 'nivel': 3,
            'subclasse': 'ordem-dos-mutantes-rework', 'ability': 'wis'}], 'escolhas': {}}
        ruleset = _apply_classes(self.person, {'classe': 'cacador'}, build)
        before = next(s for s in derive(self.person, ruleset=ruleset)['pericias']
                      if s['nome'] == 'Percepção')
        self.assertTrue(before['proficiente'])
        self.assertFalse(self.person.pericias.filter(nome='Percepção').exists())
        group = expertise_groups(self.person, build)[0]
        self.assertEqual(group['limite'], 1)
        self.assertIn('percepcao', {o['valor'] for o in group['opcoes']})
        self.assertNotIn('atletismo', {o['valor'] for o in group['opcoes']})
        build['escolhas'][group['key']] = ['percepcao']
        apply_expertise_choices(self.person, build)
        apply_expertise_choices(self.person, build)
        self.person.refresh_from_db()
        after = next(s for s in derive(self.person, ruleset=ruleset)['pericias']
                     if s['nome'] == 'Percepção')
        self.assertTrue(after['expertise'])
        self.assertEqual(after['bonus'], before['bonus'] + 2)
        self.assertEqual(expertise_groups(self.person, build)[0]['pendentes'], 0)
        self.assertEqual(self.person.escolhas.filter(tipo='hunter-expertise').count(), 1)
        self.assertFalse(self.person.pericias.filter(nome='Percepção').exists())
        for value in ('atletismo', 'not-a-skill'):
            invalid = {'escolhas': {group['key']: ['percepcao', value]}}
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_expertise_choices(self.person, invalid)

    def test_secondary_published_class_uses_revised_features_not_legacy_secrets(self):
        base = self._payload('guerreiro')
        before = TbPersonagem.objects.count()
        profiles = TbPersonagemCacador.objects.count()
        response = self.client.post(reverse('pathbuilder_preview'),
            {'base': base, 'build': self.build(ability='int')}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:500])
        result = response.json()['build']
        features = {f['nome']: f['nivel'] for f in result['features'] if f['fonte'] == 'Caçador'}
        self.assertEqual(features['Preparos de Caçada'], 2)
        self.assertEqual(features['Instinto de Caçador'], 3)
        self.assertEqual(features['Ataque Extra'], 5)
        self.assertNotIn('Segundo Ataque', features)
        self.assertNotIn('Segredos de Caçador', features)
        self.assertFalse(any(g['origem'] == 'Segredos de Caçador' for g in result['escolhas_grupos']))
        caster = next(c for c in result['conjuracao']['spellcasters'] if c['classe'] == 'Caçador')
        self.assertEqual(caster['ability'], 'INT')
        self.assertEqual(TbPersonagem.objects.count(), before)
        self.assertEqual(TbPersonagemCacador.objects.count(), profiles)

    def test_missing_permanent_ability_does_not_fall_back_to_legacy(self):
        with self.assertRaisesMessage(PathbuilderError, 'Escolha Inteligencia ou Sabedoria'):
            _apply_classes(self.person, {'classe': 'guerreiro'}, self.build())
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.ruleset_id)
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_legacy_subclass_cannot_be_selected_in_new_simulation(self):
        with self.assertRaisesMessage(PathbuilderError, 'Subclasse fora da revisao'):
            _apply_classes(self.person, {'classe': 'guerreiro'},
                           self.build(ability='int', subclasse=self.legacy.slug))
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.ruleset_id)

    def test_incompatible_publications_are_rejected_without_reassignment(self):
        other = create_class_revision(self.target.checksum, self.fighter.pk,
            [{'model': 'home.tbclasse', 'action': 'update', 'pk': self.fighter.pk,
              'fields': {'tagline': 'Different published revision'}}], presentation_source='catalog')
        TbClassPublication.objects.create(id_classe=self.fighter, ruleset=other)
        with self.assertRaises(PathbuilderError):
            _apply_classes(self.person, {'classe': 'guerreiro'}, self.build(ability='int'))
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.ruleset_id)

    def test_configured_catalog_uses_same_revision_and_exposes_ability_choices(self):
        TbClassPublication.objects.filter(id_classe=self.classe).delete()
        with override_settings(CLASS_CATALOG_RULESETS={'cacador': self.target.checksum}):
            hunter = next(row for row in catalogos()['classes'] if row['slug'] == 'cacador')
        self.assertEqual(hunter['ruleset_checksum'], self.target.checksum)
        self.assertEqual(len(hunter['subclasses']), 8)
        self.assertEqual(hunter['permanent_ability_choices'], ['int', 'wis'])
