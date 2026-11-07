"""Contrato do cadastro real, sem banco nem execução concorrente de testes PG."""
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.test import SimpleTestCase

from home.magic_workshop import spell_is_log_castable
from home.management.commands.prepare_battle_familiar import prepare_fixture
from home.models import TbClasse
from home.spell_access import spell_class_slugs


class BattleFamiliarCatalogTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.text = (cls.root / 'home/fixtures/conteudo.json').read_bytes().decode('utf-8')
        cls.reference = (cls.root / 'ref/FAMILIAR_DE_BATALHA.md').read_text(encoding='utf-8')
        cls.rows = json.loads(cls.text)

    def battle(self, rows=None):
        matches = [r for r in (self.rows if rows is None else rows)
                   if r['model'] == 'home.tbmagia'
                   and r['fields'].get('nome_ingles') == 'Battle Familiar']
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_catalog_metadata_and_complete_reference(self):
        fields = self.battle()['fields']
        self.assertEqual(fields['nome'], 'Familiar de Batalha')
        self.assertEqual(fields['nivel'], 2)
        self.assertEqual(fields['escola'], 'Conjuração')
        self.assertEqual(fields['casting_time'], 'Ação')
        self.assertEqual(fields['duracao'], '1 hora')
        self.assertEqual(fields['alcance'], '3 metros (10 pés)')
        self.assertEqual(fields['componentes'],
                         'V, S, M (um diamante no valor de pelo menos 25 PO)')
        self.assertFalse(fields['concentracao'])
        self.assertFalse(fields['ritual'])
        # Compara todo o corpo: bloco, tabela, traços, ações e interação com Find Familiar.
        start = self.reference.index('Você conjura um familiar')
        end = self.reference.index('## Usando um espaço de magia de círculo superior')
        self.assertEqual(fields['descricao'], self.reference[start:end].strip())
        self.assertEqual(fields['em_niveis_superiores'],
                         'Use o círculo do espaço gasto como círculo da magia no bloco de estatísticas.')

    def test_existing_deserializer_access_and_workshop_accept_catalog(self):
        spell = next(serializers.deserialize('json', json.dumps([self.battle()]))).object
        classes = [TbClasse(**dict(r['fields'], pk=r['pk'])) for r in self.rows
                   if r['model'] == 'home.tbclasse']
        self.assertEqual(spell.classes, 'Druida, Bruxo, Mago')
        self.assertEqual(spell_class_slugs(spell, classes=classes),
                         ['druida', 'mistico', 'mago'])
        self.assertTrue(spell_is_log_castable(spell))
        spell.tags_json = []
        self.assertFalse(spell_is_log_castable(spell))

    def test_shipped_fixture_is_idempotent_and_identities_unique(self):
        self.assertEqual(prepare_fixture(self.text, self.reference), self.text)
        spells = [r for r in self.rows if r['model'] == 'home.tbmagia']
        self.assertEqual(len({r['pk'] for r in spells}), len(spells))
        self.assertEqual(len({r['fields']['slug'] for r in spells}), len(spells))
        familiar = [r for r in spells if r['fields'].get('nome_ingles') == 'Find Familiar']
        self.assertEqual(len(familiar), 1)
        self.assertEqual((familiar[0]['pk'], familiar[0]['fields']['slug']),
                         (197, 'encontrar-familiar'))

    def test_insert_preserves_every_existing_record_and_repeats_without_change(self):
        battle = self.battle()
        original = [r for r in self.rows if r != battle]
        result = prepare_fixture(json.dumps(original, ensure_ascii=False), self.reference)
        rows = json.loads(result)
        self.assertEqual(rows[:-1], original)
        self.battle(rows)
        self.assertEqual(prepare_fixture(result, self.reference), result)

    def test_english_identity_preserves_existing_pk_slug_despite_translation(self):
        rows = json.loads(self.text)
        existing = self.battle(rows)
        existing['pk'] = 900001
        existing['fields'].update(nome='Tradução anterior', nome_ingles=' BATTLE FAMILIAR ',
                                  slug='battle-familiar-antigo')
        result = json.loads(prepare_fixture(json.dumps(rows), self.reference))
        registered = self.battle(result)
        self.assertEqual(registered['pk'], 900001)
        self.assertEqual(registered['fields']['slug'], 'battle-familiar-antigo')
        self.assertEqual(len(result), len(rows))

    def test_ambiguous_identity_and_slug_collision_fail_closed(self):
        rows = json.loads(self.text)
        duplicate = json.loads(json.dumps(self.battle(rows)))
        duplicate['pk'] = 900001
        duplicate['fields']['slug'] = 'duplicata'
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            prepare_fixture(json.dumps(rows + [duplicate]), self.reference)
        self.battle(rows)['fields']['nome_ingles'] = None
        with self.assertRaisesRegex(ValueError, 'Colisão'):
            prepare_fixture(json.dumps(rows), self.reference)

    def test_missing_find_familiar_is_not_silently_created(self):
        rows = [r for r in self.rows if not (r['model'] == 'home.tbmagia'
                and r['fields'].get('nome_ingles') == 'Find Familiar')]
        with self.assertRaisesRegex(ValueError, 'Find Familiar'):
            prepare_fixture(json.dumps(rows), self.reference)

    def test_management_command_writes_only_fixture_and_second_run_is_noop(self):
        battle = self.battle()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'conteudo.json'
            path.write_text(json.dumps([r for r in self.rows if r != battle]),
                            encoding='utf-8')
            output = StringIO()
            call_command('prepare_battle_familiar', fixture=path,
                         reference=self.root / 'ref/FAMILIAR_DE_BATALHA.md', stdout=output)
            first = path.read_bytes()
            call_command('prepare_battle_familiar', fixture=path,
                         reference=self.root / 'ref/FAMILIAR_DE_BATALHA.md', stdout=output)
            self.assertEqual(path.read_bytes(), first)
            self.assertIn('idempotente', output.getvalue())
            self.battle(json.loads(first))
