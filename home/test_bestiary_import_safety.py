import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import TbBestiario


class BestiaryImportSafetyTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'creatures.csv'

    def csv_rows(self, names):
        with self.path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['Name', 'Source'])
            writer.writeheader()
            writer.writerows({'Name': name, 'Source': 'review-test'} for name in names)

    def run_import(self, apply=False, sem_fix_magias=True):
        output = StringIO()
        with patch('home.management.commands.importar_bestiario_csv._load_spell_alignment', return_value={}):
            call_command('importar_bestiario_csv', csv=str(self.path), apply=apply,
                         sem_fix_magias=sem_fix_magias, stdout=output)
        return output.getvalue()

    def test_new_creature_is_created_once_without_new_primary_key_on_replay(self):
        self.csv_rows(['Review Beast'])
        self.assertIn('Criadas: 1', self.run_import(apply=True))
        creature = TbBestiario.objects.get(slug='review-beast')
        self.assertIn('Inalteradas: 1', self.run_import(apply=True))
        self.assertEqual(TbBestiario.objects.get(slug='review-beast').pk, creature.pk)
        self.assertEqual(TbBestiario.objects.count(), 1)

    def test_manual_edit_is_reported_and_not_overwritten(self):
        self.csv_rows(['Review Beast'])
        self.run_import(apply=True)
        creature = TbBestiario.objects.get(slug='review-beast')
        creature.nome = 'Nome revisado pela mesa'
        creature.statblock_json = {**creature.statblock_json, 'manual_note': 'Preservar'}
        creature.save(update_fields=['nome', 'statblock_json'])
        self.assertIn('Pendentes de revisao: 1', self.run_import())
        self.assertIn('Pendentes de revisao: 1', self.run_import(apply=True))
        creature.refresh_from_db()
        self.assertEqual(creature.nome, 'Nome revisado pela mesa')
        self.assertEqual(creature.statblock_json['manual_note'], 'Preservar')

    def test_english_name_match_never_renames_existing_creature(self):
        self.csv_rows(['Review Beast'])
        previous = TbBestiario.objects.create(slug='legacy-beast', nome='Legado',
                                               statblock_json={'name_en': 'Review Beast'})
        self.assertIn('nome_en ja existe sob outro slug', self.run_import(apply=True))
        previous.refresh_from_db()
        self.assertEqual(previous.slug, 'legacy-beast')
        self.assertFalse(TbBestiario.objects.filter(slug='review-beast').exists())

    def test_community_record_and_duplicate_csv_slug_are_preserved(self):
        self.csv_rows(['Review Beast'])
        author = User.objects.create_user('import_author')
        creature = TbBestiario.objects.create(slug='review-beast', nome='Criatura da comunidade',
                                               comunidade=True, autor=author)
        self.assertIn('Pendentes de revisao: 1', self.run_import(apply=True))
        creature.refresh_from_db()
        self.assertEqual((creature.nome, creature.autor_id, creature.comunidade),
                         ('Criatura da comunidade', author.pk, True))
        self.csv_rows(['Review Beast', 'Review Beast'])
        with self.assertRaisesMessage(CommandError, 'slugs repetidos'):
            self.run_import(apply=True)
        self.assertEqual(TbBestiario.objects.count(), 1)

    def test_spell_reference_failure_rolls_back_creature_creation(self):
        self.csv_rows(['Review Beast'])
        with patch('home.management.commands.importar_bestiario_csv._fix_spell_creature_refs',
                   side_effect=RuntimeError('Falha no reparo')):
            with self.assertRaisesMessage(RuntimeError, 'Falha no reparo'):
                self.run_import(apply=True, sem_fix_magias=False)
        self.assertFalse(TbBestiario.objects.filter(slug='review-beast').exists())
