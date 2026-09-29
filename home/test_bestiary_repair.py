from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .bestiary_audit import audit_snapshot
from .bestiary_repair import RepairConflict, reconcile_snapshot


class BestiaryRepairTests(SimpleTestCase):
    def rows_and_report(self):
        rows = [
            {'model': 'home.tbmagia', 'pk': 7, 'fields': {'slug': 'elementalismo', 'nome': 'Elementalismo'}},
            {'model': 'home.tbbestiario', 'pk': 11,
             'fields': {'slug': 'criatura-fonte', 'nome': 'Criatura', 'tipo': 'Elemental',
                        'tamanho': 'M', 'nd': '1', 'tags_json': ['summon:bestiary{criatura_fonte}'],
                        'statblock_json': {
                            'traits': [{'name': 'Conjuração', 'entries': ['Conjura.'],
                                        'spell_refs': [{'slug': 'Elementalismo', 'resolved': True}]}],
                            'reactions': [{'name': 'Escudo', 'entries': ['Defende.']}],
                        }}},
        ]
        report = audit_snapshot(rows)
        report['source'] = {'sha256': sha256(json.dumps(rows).encode()).hexdigest()}
        return rows, report

    def test_only_expected_reference_changes_and_replay_is_noop(self):
        rows, report = self.rows_and_report()
        original = deepcopy(rows)
        changed, counts = reconcile_snapshot(rows, report)
        self.assertEqual(counts, {'applied': 1, 'unchanged': 0})
        self.assertEqual(rows, original)
        expected = deepcopy(original)
        expected[1]['fields']['statblock_json']['traits'][0]['spell_refs'][0]['slug'] = 'elementalismo'
        self.assertEqual(changed, expected)
        again, replay = reconcile_snapshot(changed, report)
        self.assertEqual(replay, {'applied': 0, 'unchanged': 1})
        self.assertEqual(again, changed)

    def test_stale_revision_and_target_identity_abort_without_mutation(self):
        rows, report = self.rows_and_report()
        stale = deepcopy(rows)
        stale[1]['fields']['statblock_json']['reactions'][0]['entries'] = ['Edição manual.']
        with self.assertRaisesRegex(RepairConflict, 'mudou'):
            reconcile_snapshot(stale, report)
        self.assertEqual(stale[1]['fields']['statblock_json']['reactions'][0]['entries'], ['Edição manual.'])
        wrong_target = deepcopy(rows)
        wrong_target[0]['fields']['slug'] = 'magia-diferente'
        with self.assertRaisesRegex(RepairConflict, 'Identidade da magia'):
            reconcile_snapshot(wrong_target, report)

    def test_command_keeps_source_and_refuses_wrong_hash_or_existing_output(self):
        rows, report = self.rows_and_report()
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'source.json'
            audit = Path(folder) / 'audit.json'
            target = Path(folder) / 'trial.json'
            source.write_text(json.dumps(rows), encoding='utf-8')
            audit.write_text(json.dumps(report), encoding='utf-8')
            source_before = source.read_bytes()
            call_command('reconciliar_bestiario_backup', backup=str(source),
                         audit=str(audit), output=str(target))
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))[0], rows[0])
            with self.assertRaises(CommandError):
                call_command('reconciliar_bestiario_backup', backup=str(source),
                             audit=str(audit), output=str(target))
            report['source']['sha256'] = '0' * 64
            audit.write_text(json.dumps(report), encoding='utf-8')
            another = Path(folder) / 'another.json'
            with self.assertRaisesRegex(CommandError, 'hash'):
                call_command('reconciliar_bestiario_backup', backup=str(source),
                             audit=str(audit), output=str(another))
            self.assertFalse(another.exists())
