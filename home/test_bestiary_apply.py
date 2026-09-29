from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .bestiary_audit import audit_snapshot
from .models import TbBestiario, TbMagia


class BestiaryApplyTests(TestCase):
    def setUp(self):
        self.spell = TbMagia.objects.create(pk=7, nome='Elementalismo', slug='elementalismo')
        self.original = {'traits': [{'name': 'Conjuração', 'entries': ['Conjura.'],
                                     'spell_refs': [{'slug': 'Elementalismo'}]}]}
        self.creatures = [TbBestiario.objects.create(
            pk=pk, nome=f'Criatura {pk}', slug=f'criatura-{pk}',
            statblock_json=deepcopy(self.original)) for pk in (11, 12)]
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.backup = root / 'backup.json'
        self.audit = root / 'audit.json'
        rows = [{'model': 'home.tbmagia', 'pk': 7,
                 'fields': {'slug': self.spell.slug, 'nome': self.spell.nome}}]
        rows += [{'model': 'home.tbbestiario', 'pk': creature.pk,
                  'fields': {'slug': creature.slug, 'statblock_json': deepcopy(self.original)}}
                 for creature in self.creatures]
        raw = json.dumps(rows).encode()
        self.backup.write_bytes(raw)
        report = audit_snapshot(rows)
        report['source'] = {'sha256': sha256(raw).hexdigest()}
        self.audit.write_text(json.dumps(report), encoding='utf-8')

    def run_batch(self, apply=False):
        return call_command('aplicar_reparos_bestiario', backup=str(self.backup),
                            audit=str(self.audit), apply=apply)

    def test_preview_apply_and_replay_preserve_other_fields(self):
        self.run_batch()
        self.creatures[0].refresh_from_db()
        self.assertEqual(self.creatures[0].statblock_json, self.original)
        self.run_batch(apply=True)
        self.creatures[0].refresh_from_db()
        self.assertEqual(self.creatures[0].statblock_json['traits'][0]['spell_refs'][0]['slug'],
                         'elementalismo')
        self.assertEqual(self.creatures[0].statblock_json['traits'][0]['entries'], ['Conjura.'])
        self.run_batch(apply=True)
        self.assertEqual(TbBestiario.objects.count(), 2)

    def test_conflict_aborts_whole_batch_without_partial_update(self):
        edited = deepcopy(self.original)
        edited['traits'][0]['entries'] = ['Edição posterior.']
        self.creatures[1].statblock_json = edited
        self.creatures[1].save(update_fields=['statblock_json'])
        with self.assertRaisesRegex(CommandError, 'diverge'):
            self.run_batch(apply=True)
        self.creatures[0].refresh_from_db()
        self.creatures[1].refresh_from_db()
        self.assertEqual(self.creatures[0].statblock_json, self.original)
        self.assertEqual(self.creatures[1].statblock_json, edited)

    def test_tampered_report_or_spell_identity_is_rejected(self):
        report = json.loads(self.audit.read_text(encoding='utf-8'))
        report['repair_candidates'][0]['new_slug'] = 'outra-magia'
        self.audit.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesRegex(CommandError, 'não correspondem'):
            self.run_batch(apply=True)
        report = audit_snapshot(json.loads(self.backup.read_text(encoding='utf-8')))
        report['source'] = {'sha256': sha256(self.backup.read_bytes()).hexdigest()}
        self.audit.write_text(json.dumps(report), encoding='utf-8')
        self.spell.slug = 'magia-alterada'
        self.spell.save(update_fields=['slug'])
        with self.assertRaisesRegex(CommandError, 'Identidade da magia'):
            self.run_batch(apply=True)
