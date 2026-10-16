import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from .bestiary_catalog import is_statblock_placeholder
from .models import TbBestiario
from .views import _render_creature_statblock_full


class SourceBackedCompanionStatblockTests(SimpleTestCase):
    def test_steel_defender_fixture_renders_source_mechanics_without_guessing_nd(self):
        # Source: ref/Classes/Artificer in Bonfire Tales RPG _ World Anvil.html
        # SHA-256: 9439579618b1f5769e6c16d6d1d6edde7570dd1b80cd5426c9e331040ca6e250
        path = Path(settings.BASE_DIR) / 'home' / 'fixtures' / 'conteudo.json'
        records = json.loads(path.read_text(encoding='utf-8'))
        matching = [record for record in records
                    if record['model'] == 'home.tbbestiario'
                    and record['fields'].get('slug') == 'defensor-de-aco']
        self.assertEqual(len(matching), 1)
        record = matching[0]
        self.assertEqual(record['pk'], 27)
        fields = record['fields']
        statblock = fields['statblock_json']
        self.assertTrue(fields['escala_com_dono'])
        self.assertIsNone(fields['nd'])
        self.assertEqual(statblock['size'], 'M')
        self.assertEqual(statblock['abilities'],
                         {'str': 14, 'dex': 12, 'con': 14, 'int': 10, 'wis': 10, 'cha': 6})
        self.assertEqual([part['name'] for part in statblock['trait']],
                         ['Vigilante', 'Ligação Arcana'])
        self.assertEqual([part['name'] for part in statblock['action']],
                         ['Golpe Fortalecido por Energia', 'Reparo (PB/Dia)'])
        self.assertEqual([part['name'] for part in statblock['reaction']],
                         ['Defletir Ataque'])
        self.assertIn('20 + 10 vezes o seu nível após o terceiro', fields['pv'])
        self.assertIn('2d8', statblock['action'][0]['entries'][0])
        self.assertIn('cond_immune:enfeiticado', fields['tags_json'][1])
        self.assertIn('immune:veneno', fields['tags_json'][1])
        self.assertFalse(is_statblock_placeholder(statblock))

        creature = TbBestiario(
            nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
            tamanho=fields['tamanho'], ca=fields['ca'], pv=fields['pv'],
            statblock_json=statblock,
        )
        html = _render_creature_statblock_full(creature)
        for text in ('Ligação Arcana', 'Golpe Fortalecido por Energia',
                     'Reparo (PB/Dia)', 'Defletir Ataque', 'Imunidades a dano',
                     'Imunidades a condicao'):
            self.assertIn(text, html)
        self.assertNotIn('Statblock incompleto:', html)
