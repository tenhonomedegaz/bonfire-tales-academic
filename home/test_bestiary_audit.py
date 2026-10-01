from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .bestiary_audit import audit_snapshot, statblock_hash


class BestiarySnapshotAuditTests(SimpleTestCase):
    def sample(self):
        return [
            {'model': 'home.tbmagia', 'pk': 7,
             'fields': {'slug': 'elementalismo', 'nome': 'Elementalismo'}},
            {'model': 'home.tbbestiario', 'pk': 11,
             'fields': {'slug': 'espirito-elemental', 'tipo': 'Elemental',
                        'tamanho': 'Small or Medium', 'nd': '1/4 (XP 50)',
                        'tags_json': ['summon:bestiary{espirito_elemental}'],
                        'statblock_json': {
                            'traits': [{'name': 'Conjuração', 'entries': ['Conjura.'],
                                        'spell_refs': [{'slug': 'Elementalismo', 'resolved': True}]}],
                            'actions': [{'name': 'Toque', 'entries': ['Causa dano.']}],
                        }}},
        ]

    def test_feature_tag_syntax_is_reported_per_creature(self):
        rows = self.sample()
        statblock = rows[1]['fields']['statblock_json']
        statblock['traits'][0]['tags_json'] = ['instant{unknown_verb:1}']
        statblock['actions'][0]['tags_json'] = ['instant{dmg:2d6(fogo)']
        report = audit_snapshot(rows)
        mechanics = report['records'][0]['mechanics']
        self.assertEqual(mechanics['syntax_error_count'], 1)
        self.assertEqual(mechanics['syntax_warning_count'], 1)
        self.assertIn('actions[0]:tag_syntax_error:desbalanceado', report['records'][0]['issues'])
        self.assertIn('traits[0]:tag_syntax_warning:verbo-desconhecido', report['records'][0]['issues'])
        self.assertEqual(report['summary']['tag_syntax_errors'], 1)
        self.assertEqual(report['summary']['tag_syntax_warnings'], 1)

    def test_legacy_source_tags_are_pending_without_false_dsl_errors(self):
        rows = self.sample()
        rows[1]['fields']['statblock_json']['actions'][0]['tags'] = [
            'cast{spell:detectar-magia, at-will}',
        ]
        report = audit_snapshot(rows)
        record = report['records'][0]
        self.assertEqual(record['mechanics']['legacy_tagged_count'], 1)
        self.assertEqual(record['mechanics']['untagged_count'], 2)
        self.assertEqual(record['mechanics']['syntax_error_count'], 0)
        self.assertIn('actions[0]:legacy_tags_need_review', record['issues'])

    def test_full_record_keeps_resolvable_aliases_separate_from_errors(self):
        rows = self.sample()
        result = audit_snapshot(rows)
        self.assertEqual(result['summary']['creatures'], 1)
        self.assertEqual(result['summary']['features'], 2)
        self.assertEqual(result['summary']['untagged_features'], 2)
        record = result['records'][0]
        self.assertEqual(record['classification']['sizes'], ['S', 'M'])
        self.assertEqual(record['classification']['cr'], 'nd:1/4')
        self.assertNotIn('tags_json[0]:unresolved_bestiary_ref', record['issues'])
        self.assertEqual(result['summary']['consumer_references'], 1)
        self.assertEqual(result['consumer_references'][0]['status'], 'resolved')
        self.assertEqual(record['references']['inbound_bestiary_count'], 1)
        self.assertEqual(record['mechanics']['status'], 'pending_semantic_review')
        candidate = result['repair_candidates'][0]
        self.assertEqual(candidate['spell_pk'], 7)
        self.assertEqual(candidate['path'], ['traits', 0, 'spell_refs', 0, 'slug'])
        self.assertEqual(candidate['expected_statblock_sha256'],
                         statblock_hash(rows[1]['fields']['statblock_json']))
        self.assertEqual(rows[1]['fields']['statblock_json']['traits'][0]['spell_refs'][0]['slug'],
                         'Elementalismo')

    def test_missing_reference_is_reported_without_repair_guess(self):
        rows = self.sample()
        rows[1]['fields']['statblock_json']['traits'][0]['spell_refs'][0]['slug'] = 'magia-inexistente'
        result = audit_snapshot(rows)
        self.assertIn('traits.0.spell_refs.0:unresolved_spell_ref', result['records'][0]['issues'])
        self.assertEqual(result['repair_candidates'], [])

    def test_variable_type_is_audited_as_multiple_explicit_types(self):
        rows = self.sample()
        rows[1]['fields']['tipo'] = 'Celestial, Fey, or Fiend'
        record = audit_snapshot(rows)['records'][0]
        self.assertEqual(record['classification']['types'],
                         ['celestial', 'feerico', 'corruptor'])
        self.assertNotIn('type_needs_classification', record['issues'])

    def test_owner_scaled_companion_keeps_missing_nd_pending(self):
        rows = self.sample()
        fields = rows[1]['fields']
        fields.update(escala_com_dono=True, companheiro_classe=5,
                      companheiro_subclasse=125, tamanho=None, nd=None)
        record = audit_snapshot(rows)['records'][0]
        self.assertEqual(record['classification']['usage'],
                         ['owner_scaled', 'linked_companion'])
        self.assertEqual(record['classification']['cr'], 'pending')
        self.assertIn('cr_needs_review', record['issues'])

    def test_dynamic_reference_is_not_misreported_as_missing_creature(self):
        rows = self.sample()
        rows.append({'model': 'home.tbtracoracial', 'pk': 21,
                     'fields': {'tags_json': ['summon:bestiary{familiar(creature_type:pick:tipo)}']}})
        result = audit_snapshot(rows)
        self.assertEqual(result['summary']['consumer_references_dynamic'], 1)
        self.assertEqual(result['summary']['consumer_references_unresolved'], 0)

    def test_command_writes_separate_report_and_refuses_overwrite(self):
        rows = self.sample()
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'original.json'
            output = Path(folder) / 'report.json'
            source.write_text(json.dumps(rows), encoding='utf-8')
            original_hash = sha256(source.read_bytes()).hexdigest()
            call_command('auditar_bestiario_backup', backup=str(source), output=str(output))
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(report['source']['sha256'], original_hash)
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), original_hash)
            with self.assertRaises(CommandError):
                call_command('auditar_bestiario_backup', backup=str(source), output=str(source))
            with self.assertRaises(CommandError):
                call_command('auditar_bestiario_backup', backup=str(source), output=str(output))
