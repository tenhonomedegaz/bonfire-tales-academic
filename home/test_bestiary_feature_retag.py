import csv
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from home.bestiary_audit import statblock_hash
from home.bestiary_feature_retag import source_entries_hash
from home.bestiary_feature_retag import FeatureRetagConflict, reviewed_statblock
from home.management.commands.importar_bestiario_csv import _split_secao
from home.models import TbBestiario


class ReviewedFeatureRetagTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.csv = Path(self.temp.name) / 'source.csv'
        self.manifest = Path(self.temp.name) / 'review.json'
        self.rows = [
            ('Test Bear', 'Rend. Melee Attack Roll: +4, reach 5 ft. Hit: 5 (1d6 + 2) Slashing damage.'),
            ('Test Wolf', 'Bite. Melee Attack Roll: +5, reach 5 ft. Hit: 5 (1d4 + 3) Piercing damage.'),
        ]
        with self.csv.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['Name', 'Actions'])
            writer.writeheader()
            writer.writerows({'Name': name, 'Actions': actions} for name, actions in self.rows)
        specs = [('test-bear', 'Despedaçar', 'instant{attack:melee, attack:+4, reach:5ft, dmg:1d6+2(cortante)}'),
                 ('test-wolf', 'Mordida', 'instant{attack:melee, attack:+5, reach:5ft, dmg:1d4+3(perfurante)}')]
        manifest_rows = []
        for (name, text), (slug, translated, tag) in zip(self.rows, specs):
            original = _split_secao(text, {})[0]
            sb = {'name_en': name, 'actions': [{'name': translated,
                  'name_en': original['name_en'], 'entries': ['Texto traduzido.'],
                  'entries_en': original['entries']}], 'traits': [{'name': 'Intocado', 'entries': ['Regra.']}]}
            creature = TbBestiario.objects.create(nome=name, slug=slug, statblock_json=sb)
            revised = deepcopy(sb)
            revised['actions'][0]['tags_json'] = [tag]
            manifest_rows.append({'pk': creature.pk, 'slug': slug,
                                  'before_sha256': statblock_hash(sb),
                                  'after_sha256': statblock_hash(revised),
                                  'features': [{'index': 0, 'name_en': original['name_en'],
                                                'source_entries_sha256': source_entries_hash(original['entries']),
                                                'tags': [tag]}]})
        self.payload = {'version': 1, 'source_sha256': sha256(self.csv.read_bytes()).hexdigest(),
                        'rows': manifest_rows}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.payload), encoding='utf-8')

    def run_command(self, apply=False):
        arguments = {'manifest': str(self.manifest), 'csv': str(self.csv)}
        if apply:
            arguments['apply'] = True
        call_command('aplicar_retagging_bestiario', **arguments)

    def test_preflight_apply_replay_and_other_content_preserved(self):
        self.run_command()
        self.assertFalse(TbBestiario.objects.get(slug='test-bear').statblock_json['actions'][0].get('tags_json'))
        self.run_command(apply=True)
        before = list(TbBestiario.objects.order_by('slug').values_list('statblock_json', flat=True))
        self.run_command(apply=True)
        self.assertEqual(before, list(TbBestiario.objects.order_by('slug').values_list('statblock_json', flat=True)))
        self.assertEqual(before[0]['traits'][0]['name'], 'Intocado')
        self.assertEqual(before[0]['actions'][0]['entries'], ['Texto traduzido.'])
        self.payload['rows'][0]['features'][0]['name_en'] = 'Outra habilidade'
        self.write_manifest()
        with self.assertRaises(CommandError):
            self.run_command(apply=True)

    def test_second_conflict_rolls_back_first_creature(self):
        wolf = TbBestiario.objects.get(slug='test-wolf')
        wolf.statblock_json = {**wolf.statblock_json, 'hp': 99}
        wolf.save(update_fields=['statblock_json'])
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(TbBestiario.objects.get(slug='test-bear').statblock_json['actions'][0].get('tags_json'))

    def test_changed_csv_or_mechanic_is_rejected(self):
        self.payload['rows'][0]['features'][0]['tags'] = ['instant{attack:melee, dmg:99d99(cortante)}']
        self.write_manifest()
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertFalse(TbBestiario.objects.get(slug='test-bear').statblock_json['actions'][0].get('tags_json'))
        self.csv.write_text(self.csv.read_text(encoding='utf-8').replace('Slashing', 'Fire'), encoding='utf-8')
        with self.assertRaises(CommandError):
            self.run_command()

    def test_reviewed_dual_range_corrects_display_and_keeps_source(self):
        source = {'Name': 'Test Archer', 'Actions':
                  'Bow. Ranged Attack Roll: +3, range 80/320 ft. Hit: 5 (1d8 + 1) Piercing damage.'}
        original = _split_secao(source['Actions'], {})[0]
        sb = {'name_en': 'Test Archer', 'actions': [{
            'name': 'Arco', 'name_en': 'Bow',
            'entries_en': original['entries'],
            'entries': ['Rolagem de Ataque à Distância: +3, alcance 80/96 m [320 pés] '
                        'Acerto: 5 (1d8 + 1) Dano perfurante.']}]}
        creature = TbBestiario.objects.create(nome='Arqueiro', slug='test-archer', statblock_json=sb)
        tag = 'instant{attack:ranged, attack:+3, range:80/320ft, dmg:1d8+1(perfurante)}'
        expected = deepcopy(sb)
        expected['actions'][0]['entries'][0] = expected['actions'][0]['entries'][0].replace(
            'alcance 80/96 m [320 pés]', 'alcance 24/96 m [80/320 pés]')
        expected['actions'][0]['tags_json'] = [tag]
        proposal = {'pk': creature.pk, 'slug': creature.slug,
                    'before_sha256': statblock_hash(sb), 'after_sha256': statblock_hash(expected),
                    'features': [{'index': 0, 'name_en': 'Bow',
                                  'source_entries_sha256': source_entries_hash(original['entries']),
                                  'tags': [tag], 'correct_dual_range': True}]}
        revised, changed = reviewed_statblock(creature, source, proposal)
        self.assertTrue(changed)
        self.assertEqual(revised, expected)
        creature.statblock_json = revised
        self.assertFalse(reviewed_statblock(creature, source, proposal)[1])
        tagged_before = deepcopy(sb)
        tagged_before['actions'][0]['tags_json'] = [tag]
        tagged_proposal = {**proposal, 'before_sha256': statblock_hash(tagged_before)}
        creature.statblock_json = tagged_before
        corrected, changed = reviewed_statblock(creature, source, tagged_proposal)
        self.assertTrue(changed)
        self.assertEqual(corrected, expected)
        creature.statblock_json = {**sb, 'actions': [{**sb['actions'][0], 'entries': ['Outro alcance.']}]}
        with self.assertRaises(FeatureRetagConflict):
            reviewed_statblock(creature, source, proposal)
