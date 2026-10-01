import csv
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .management.commands.importar_bestiario_csv import _fields_for_row
from .models import TbBestiario


class ReviewedBestiaryImportTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.csv_path = Path(temporary.name) / 'creatures.csv'
        self.manifest_path = Path(temporary.name) / 'review.json'

    def source(self, names):
        with self.csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['Name', 'Source'])
            writer.writeheader()
            writer.writerows({'Name': name, 'Source': 'review-test'} for name in names)

    def existing(self, name):
        slug, fields = _fields_for_row({'Name': name, 'Source': 'review-test'}, [])
        creature = TbBestiario.objects.create(slug=slug, **fields)
        creature.nome = 'Nome da mesa: ' + name
        creature.statblock_json = {**creature.statblock_json, 'manual_note': 'Preservar'}
        creature.imagem_url = '/media/propria.png'
        creature.save(update_fields=['nome', 'statblock_json', 'imagem_url'])
        return creature

    def command(self, apply=False):
        output = StringIO()
        with patch('home.management.commands.revisar_importacao_bestiario._load_spell_alignment',
                   return_value={}):
            call_command('revisar_importacao_bestiario', csv=str(self.csv_path),
                         **({'manifest': str(self.manifest_path), 'apply': True} if apply else
                            {'output': str(self.manifest_path)}), stdout=output)
        return output.getvalue()

    def approve(self, fields_by_slug):
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        for row in manifest['rows']:
            row['approved_fields'] = fields_by_slug.get(row['slug'], [])
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    def test_selected_field_updates_and_replay_preserve_manual_data(self):
        self.source(['Review Beast'])
        creature = self.existing('Review Beast')
        self.command()
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.assertIn('nome', manifest['rows'][0]['changes'])
        self.assertIn('statblock_json', manifest['rows'][0]['changes'])
        self.assertEqual(manifest['rows'][0]['approved_fields'], [])
        approved_name = manifest['rows'][0]['changes']['nome']['proposed']
        self.approve({'review-beast': ['nome']})
        self.assertIn('Aplicado: 1', self.command(apply=True))
        creature.refresh_from_db()
        self.assertEqual(creature.nome, approved_name)
        self.assertEqual(creature.statblock_json['manual_note'], 'Preservar')
        self.assertEqual(creature.imagem_url, '/media/propria.png')
        self.assertIn('ja aplicado: 1', self.command(apply=True))

    def test_name_approval_updates_only_public_labels(self):
        self.source(['Fire Elemental'])
        creature = self.existing('Fire Elemental')
        creature.descricao_markdown = f'### {creature.nome}\n\nTexto da mesa.'
        creature.save(update_fields=['descricao_markdown'])
        original_statblock = dict(creature.statblock_json)
        self.command()
        self.approve({'fire-elemental': ['nome']})
        self.assertIn('Aplicado: 1', self.command(apply=True))
        creature.refresh_from_db()
        self.assertEqual(creature.statblock_json, {
            **original_statblock, 'name': creature.nome,
        })
        self.assertEqual(creature.descricao_markdown,
                         f'### {creature.nome}\n\nTexto da mesa.')
        self.assertEqual(creature.imagem_url, '/media/propria.png')
        self.assertIn('ja aplicado: 1', self.command(apply=True))

    def test_name_approval_rejects_divergent_title(self):
        self.source(['Fire Elemental'])
        creature = self.existing('Fire Elemental')
        creature.descricao_markdown = '### Outro titulo\nTexto da mesa.'
        creature.save(update_fields=['descricao_markdown'])
        self.command()
        self.approve({'fire-elemental': ['nome']})
        with self.assertRaisesMessage(CommandError, 'Titulos divergentes'):
            self.command(apply=True)
        creature.refresh_from_db()
        self.assertEqual(creature.nome, 'Nome da mesa: Fire Elemental')

    def test_name_approval_cannot_bundle_full_statblock(self):
        self.source(['Fire Elemental'])
        creature = self.existing('Fire Elemental')
        creature.descricao_markdown = f'### {creature.nome}\nTexto da mesa.'
        creature.save(update_fields=['descricao_markdown'])
        self.command()
        self.approve({'fire-elemental': ['nome', 'statblock_json']})
        with self.assertRaisesMessage(CommandError, 'Aprovar nome separadamente'):
            self.command(apply=True)

    def test_stale_second_row_rolls_back_first_update(self):
        self.source(['Review Beast', 'Review Dragon'])
        first, second = self.existing('Review Beast'), self.existing('Review Dragon')
        self.command()
        self.approve({'review-beast': ['nome'], 'review-dragon': ['nome']})
        second.descricao_markdown = 'Edicao posterior'
        second.save(update_fields=['descricao_markdown'])
        with self.assertRaisesMessage(CommandError, 'Criatura mudou desde a revisao'):
            self.command(apply=True)
        first.refresh_from_db()
        self.assertEqual(first.nome, 'Nome da mesa: Review Beast')

    def test_source_change_and_community_record_reject_approval(self):
        self.source(['Review Beast'])
        creature = self.existing('Review Beast')
        self.command()
        self.approve({'review-beast': ['nome']})
        self.source(['Review Beast', 'Other Beast'])
        with self.assertRaisesMessage(CommandError, 'Manifesto nao corresponde ao CSV'):
            self.command(apply=True)
        self.source(['Review Beast'])
        creature.comunidade = True
        creature.save(update_fields=['comunidade'])
        with self.assertRaisesMessage(CommandError, 'Identidade divergente'):
            self.command(apply=True)
        creature.refresh_from_db()
        self.assertEqual(creature.nome, 'Nome da mesa: Review Beast')

    def test_unreviewable_field_and_wrong_primary_key_are_rejected(self):
        self.source(['Review Beast'])
        creature = self.existing('Review Beast')
        self.command()
        self.approve({'review-beast': ['comunidade']})
        with self.assertRaisesMessage(CommandError, 'Campos aprovados invalidos'):
            self.command(apply=True)
        self.approve({'review-beast': ['nome']})
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        manifest['rows'][0]['pk'] = creature.pk + 100
        self.manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'Identidade divergente'):
            self.command(apply=True)
        creature.refresh_from_db()
        self.assertEqual(creature.nome, 'Nome da mesa: Review Beast')


class ReviewedSourceMetadataTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.csv_path = Path(temporary.name) / 'source.csv'
        self.manifest_path = Path(temporary.name) / 'review.json'

    def seed(self, names=('Fire Wolf',)):
        with self.csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                'Name', 'Source', 'Size', 'Type', 'Alignment', 'CR', 'Actions'])
            writer.writeheader()
            writer.writerows({'Name': name, 'Source': 'review-test', 'Size': 'Medium',
                              'Type': 'Beast', 'Alignment': 'unaligned', 'CR': '1',
                              'Actions': 'Bite. The wolf bites a target.'} for name in names)
        creatures = []
        for name in names:
            creatures.append(TbBestiario.objects.create(
                slug=name.lower().replace(' ', '-'), nome='Lobo da Mesa',
                tipo='Besta', tamanho='Medio', nd='1',
                imagem_url='/media/manual.png',
                statblock_json={
                    'name': 'Lobo da Mesa', 'name_en': 'Fogo Wolf',
                    'size_en': 'Medio', 'type_en': 'Besta',
                    'alignment_en': 'sem alinhamento', 'cr': '1',
                    'actions': [{'name': 'Mordida', 'name_en': 'Bite',
                                 'entries': ['Texto da mesa, preservado.']}],
                    'manual_note': 'Preservar',
                }, tags_json=['manual:preservar']))
        return creatures

    def command(self, apply=False):
        output = StringIO()
        call_command('revisar_importacao_bestiario', csv=str(self.csv_path),
                     source_metadata=True,
                     **({'manifest': str(self.manifest_path), 'apply': True} if apply else
                        {'output': str(self.manifest_path)}), stdout=output)
        return output.getvalue()

    def approve(self):
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        for row in manifest['rows']:
            row['approved_fields'] = list(row['proposed_fields'])
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    def test_source_metadata_repair_is_narrow_and_idempotent(self):
        creature = self.seed()[0]
        self.assertIn('1 propostas', self.command())
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['rows'][0]['approved_fields'], [])
        self.assertEqual(manifest['rows'][0]['proposed_fields']['name_en'], 'Fire Wolf')
        self.approve()
        self.assertIn('Aplicado: 1', self.command(apply=True))
        creature.refresh_from_db()
        self.assertEqual([creature.statblock_json[key] for key in
                          ('name_en', 'size_en', 'type_en', 'alignment_en')],
                         ['Fire Wolf', 'Medium', 'Beast', 'unaligned'])
        self.assertEqual(creature.statblock_json['actions'][0]['entries'],
                         ['Texto da mesa, preservado.'])
        self.assertEqual(creature.statblock_json['manual_note'], 'Preservar')
        self.assertEqual(creature.imagem_url, '/media/manual.png')
        self.assertEqual(creature.tags_json, ['manual:preservar'])
        self.assertIn('ja aplicado: 1', self.command(apply=True))

    def test_stale_record_rolls_back_first_repair(self):
        first, second = self.seed(('Fire Wolf', 'Fire Bear'))
        self.command()
        self.approve()
        second.statblock_json['manual_note'] = 'Edicao posterior'
        second.save(update_fields=['statblock_json'])
        with self.assertRaisesMessage(CommandError, 'Criatura mudou desde a revisao'):
            self.command(apply=True)
        first.refresh_from_db()
        self.assertEqual(first.statblock_json['name_en'], 'Fogo Wolf')

    def test_changed_source_or_adulterated_proposal_is_rejected(self):
        creature = self.seed()[0]
        self.command()
        self.approve()
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        manifest['rows'][0]['proposed_fields']['name_en'] = 'Other Wolf'
        self.manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'Proposta adulterada'):
            self.command(apply=True)
        creature.refresh_from_db()
        self.assertEqual(creature.statblock_json['name_en'], 'Fogo Wolf')
        self.seed_source_changed()
        with self.assertRaisesMessage(CommandError, 'Manifesto nao corresponde ao CSV'):
            self.command(apply=True)

    def test_feature_boundary_and_community_record_remain_pending(self):
        first, second = self.seed(('Fire Wolf', 'Fire Bear'))
        first.statblock_json['actions'][0]['name_en'] = 'Claw'
        first.save(update_fields=['statblock_json'])
        second.comunidade = True
        second.save(update_fields=['comunidade'])
        self.command()
        report = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(report['rows'], [])
        self.assertEqual({item['slug']: item['reason'] for item in report['pending']},
                         {'fire-wolf': 'actions_divergente',
                          'fire-bear': 'registro_nao_importado_ou_editado'})

    def seed_source_changed(self):
        with self.csv_path.open('a', encoding='utf-8') as handle:
            handle.write('Other Wolf,review-test,Medium,Beast,unaligned,1,')
