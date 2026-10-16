import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from .bestiary_catalog import is_statblock_placeholder, type_keys, size_keys
from .models import TbBestiario
from .views import _render_creature_statblock_full


class SourceBackedCompanionStatblockTests(SimpleTestCase):
    def test_cleric_and_mystic_companions_keep_source_mechanics_and_filters(self):
        # Sources: local World Anvil class pages for Cleric and Mystic.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, slug, kind, traits, action, formula, snippet in (
            (15, 'ajudante-da-natureza', 'planta ou besta', 2,
             'Golpe da Natureza', '10 + 5 vezes o seu nível', '1d8'),
            (19, 'espirito-das-profundezas', 'monstruosidade', 3,
             'Golpe das Profundezas', '5 + 3 vezes o seu nível total.', '2d8'),
        ):
            matches = [r for r in records if r['model'] == 'home.tbbestiario'
                       and r['pk'] == pk]
            self.assertEqual(len(matches), 1)
            fields = matches[0]['fields']
            self.assertEqual(fields['slug'], slug)
            self.assertEqual(fields['tipo'], kind)
            self.assertEqual(fields['tamanho'], 'M')
            self.assertEqual(size_keys(fields['tamanho']), ('M',))
            self.assertEqual(fields['pv'], formula)
            self.assertTrue(fields['escala_com_dono'])
            self.assertIsNone(fields['nd'])
            sb = fields['statblock_json']
            self.assertEqual(len(sb['trait']), traits)
            self.assertEqual(sb['action'][0]['name'], action)
            self.assertIn(snippet, sb['action'][0]['entries'][0])
            self.assertFalse(is_statblock_placeholder(sb))
            creature = TbBestiario(nome=fields['nome'], slug=slug, tipo=kind,
                                   tamanho='M', ca=fields['ca'], pv=fields['pv'],
                                   statblock_json=sb)
            rendered = _render_creature_statblock_full(creature)
            self.assertIn(action, rendered)
            self.assertNotIn('Statblock incompleto:', rendered)
        self.assertEqual(type_keys('planta ou besta'), ('planta', 'besta'))
        self.assertEqual(type_keys('monstruosidade'), ('monstruosidade',))
        helper = next(r['fields']['statblock_json'] for r in records
                      if r['model'] == 'home.tbbestiario' and r['pk'] == 15)
        self.assertIn('Percepção Passiva 13 + (BP)', helper['senses'])
        depths = next(r['fields']['statblock_json'] for r in records
                      if r['model'] == 'home.tbbestiario' and r['pk'] == 19)
        self.assertIn('Voo: 9 Metros', depths['speed'])
        self.assertIn('Nado: 18 Metros', depths['speed'])
        self.assertIn('5º nível', depths['trait'][1]['entries'][0])
        self.assertIn('14º nível', depths['trait'][1]['entries'][0])
        self.assertEqual(depths['damage_immunities'], 'Frio')

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
