import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from .bestiary_catalog import is_statblock_placeholder, type_keys, size_keys
from .models import TbBestiario
from .views import _render_creature_statblock_full


class SourceBackedCompanionStatblockTests(SimpleTestCase):
    def test_source_backed_summons_preserve_spell_rules_and_stats(self):
        # Bestiary.csv: PHB'24 pp. 323/326 and XGE p. 169; spells 490/96/529.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        cases = (
            (40, 490, 'espirito-bestial', 'S', 18, '11 + nível da magia',
             '20 (Ar) ou 30 (Terra/Água)', 'Dilacerar'),
            (46, 96, 'espirito-feerico', 'S', 13, '12 + nível da magia',
             '30 + 10 por nível', 'Passo Feérico'),
            (49, 529, 'pequeno-servo', 'T', 4, '15 (Armadura Natural)',
             '10 (4d4)', 'Pancada'),
        )
        for pk, spell_pk, slug, size, strength, ac, hp, action in cases:
            fields = next(r['fields'] for r in records
                          if r['model'] == 'home.tbbestiario' and r['pk'] == pk)
            spell = next(r['fields'] for r in records
                         if r['model'] == 'home.tbmagia' and r['pk'] == spell_pk)
            self.assertEqual(fields['slug'], slug)
            self.assertIn(slug, spell['descricao'])
            self.assertEqual(fields['tamanho'], size)
            self.assertIsNone(fields['nd'])
            self.assertTrue(fields['escala_com_dono'])
            self.assertEqual(fields['statblock_json']['abilities']['str'], strength)
            self.assertEqual(fields['ca'], ac)
            self.assertIn(hp, fields['pv'])
            sb = fields['statblock_json']
            self.assertFalse(is_statblock_placeholder(sb))
            creature = TbBestiario(nome=fields['nome'], slug=slug,
                                   tipo=fields['tipo'], tamanho=size,
                                   ca=ac, pv=fields['pv'], statblock_json=sb)
            self.assertIn(action, _render_creature_statblock_full(creature))

    def test_homunculus_servant_combines_official_stats_with_local_commands(self):
        # Eberron official errata, Homunculus Servant; fixture spell 272.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario'
                      and record['pk'] == 41)
        self.assertEqual(fields['slug'], 'servo-homunculo')
        self.assertEqual(size_keys(fields['tamanho']), ('T',))
        self.assertIsNone(fields['nd'])
        self.assertTrue(fields['escala_com_dono'])
        sb = fields['statblock_json']
        self.assertEqual(sb['abilities'], {
            'str': 4, 'dex': 15, 'con': 12,
            'int': 10, 'wis': 10, 'cha': 7,
        })
        self.assertFalse(is_statblock_placeholder(sb))
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], tamanho=fields['tamanho'],
                               ca=fields['ca'], pv=fields['pv'], statblock_json=sb)
        html = _render_creature_statblock_full(creature)
        for phrase in ('Evasão', 'Golpe de Energia', 'Canalizar Magia',
                       'Comando do Invocador', '1 + modificador de Inteligência',
                       '13 (Armadura Natural)'):
            self.assertIn(phrase, html)
        self.assertNotIn('Statblock incompleto:', html)
        spell = next(record['fields'] for record in records
                     if record['model'] == 'home.tbmagia'
                     and record['pk'] == 272)
        self.assertIn('servo-homunculo', spell['descricao'])

    def test_trickery_domain_illusions_keep_distinct_source_mechanics(self):
        # Source: ref/Classes Reworkadas/Clerigo ... World Anvil.html,
        # Dominio da Trapaca, Invocar Duplicidade and Baile das Mascaras.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, slug, required in (
            (18, 'duplicata-ilusoria', ('Onde o Golpe Erra', 'três duplicatas',
                                       '1d20', '11 ou mais', '2d10')),
            (22, 'ilusao-de-si', ('Invocar Duplicidade', 'Canalizar Divindade',
                                 '3º nível', '6º', '17º', '36 metros',
                                 'não realiza ações')),
        ):
            fields = next(record['fields'] for record in records
                          if record['model'] == 'home.tbbestiario'
                          and record['pk'] == pk)
            self.assertEqual(fields['slug'], slug)
            self.assertEqual(fields['companheiro_classe'], 5)
            self.assertEqual(fields['companheiro_subclasse'], 129)
            self.assertIsNone(fields['ca'])
            self.assertIsNone(fields['pv'])
            self.assertIsNone(fields['nd'])
            sb = fields['statblock_json']
            self.assertFalse(is_statblock_placeholder(sb))
            creature = TbBestiario(nome=fields['nome'], slug=slug,
                                   tipo=fields['tipo'], statblock_json=sb)
            html = _render_creature_statblock_full(creature)
            for phrase in required:
                self.assertIn(phrase, html)
            self.assertNotIn('Statblock incompleto:', html)

    def test_owner_scaled_feature_objects_render_without_invented_base_stats(self):
        # Fixture abilities 761 (Fiel Montaria) and 1411 (Realidade Ilusoria).
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, slug, subclass, required in (
            (21, 'fiel-montaria', 34, ('Vínculo da Fiel Montaria',
                                     'metade dos seus PV máximos', '1,5 metro')),
            (24, 'objeto-ilusorio', 59, ('Realidade Ilusória',
                                       'CD de magia do Mago', '3 vezes o nível de Mago',
                                       '1 minuto')),
        ):
            fields = next(record['fields'] for record in records
                          if record['model'] == 'home.tbbestiario'
                          and record['pk'] == pk)
            self.assertEqual(fields['slug'], slug)
            self.assertEqual(fields['companheiro_subclasse'], subclass)
            self.assertTrue(fields['escala_com_dono'])
            self.assertIsNone(fields['tamanho'])
            self.assertIsNone(fields['nd'])
            sb = fields['statblock_json']
            self.assertFalse(is_statblock_placeholder(sb))
            creature = TbBestiario(nome=fields['nome'], slug=slug,
                                   tipo=fields['tipo'], tamanho=fields['tamanho'],
                                   ca=fields['ca'], pv=fields['pv'], statblock_json=sb)
            rendered = _render_creature_statblock_full(creature)
            for phrase in required:
                self.assertIn(phrase, rendered)
            self.assertNotIn('Statblock incompleto:', rendered)
        self.assertIsNone(next(record['fields'] for record in records
                               if record['model'] == 'home.tbbestiario'
                               and record['pk'] == 21)['ca'])

    def test_otherworldly_steed_preserves_spell_scaling_and_three_forms(self):
        # SRD 5.2.1, Find Steed / Otherworldly Steed, p. 130-131.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario' and record['pk'] == 39)
        self.assertEqual(fields['slug'], 'corcel-de-outro-mundo')
        self.assertEqual(type_keys(fields['tipo']), ('celestial', 'feerico', 'corruptor'))
        self.assertEqual(size_keys(fields['tamanho']), ('L',))
        self.assertIsNone(fields['nd'])
        self.assertTrue(fields['escala_com_dono'])
        sb = fields['statblock_json']
        self.assertFalse(is_statblock_placeholder(sb))
        self.assertEqual(sb['abilities'], {
            'str': 18, 'dex': 12, 'con': 14,
            'int': 6, 'wis': 12, 'cha': 8,
        })
        self.assertEqual(len(sb['bonus']), 3)
        self.assertIn('1d8 + nível da magia', sb['action'][0]['entries'][0])
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], tamanho=fields['tamanho'],
                               nd=fields['nd'], ca=fields['ca'], pv=fields['pv'],
                               statblock_json=sb)
        html = _render_creature_statblock_full(creature)
        for phrase in ('Golpe de Outro Mundo', 'Olhar Aterrador',
                       'Passo Feérico', 'Toque Curativo', '4º nível',
                       '10 + 1 por nível', '5 + 10 por nível'):
            self.assertIn(phrase, html)
        self.assertNotIn('Statblock incompleto:', html)

    def test_wizard_objects_show_conjuration_and_transmutation_rules(self):
        # Source: ref/Classes/Mago ... World Anvil.html, Conjurador and Transmutador.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, slug, subclass, trait, required in (
            (23, 'objeto-conjurado', 51, 'Conjuração Menor',
             ('Requisitos:', 'Restrições:', 'Estatísticas:', 'Duração:',
              '1 hora', '9º círculo')),
            (25, 'pedra-filosofal', 61, 'Mestre da Transmutação',
             ('Panaceia:', 'Transmutação Maior:', 'Restaurar Vida:',
              'Restaurar Juventude:', 'Potencializar Magia:')),
        ):
            fields = next(record['fields'] for record in records
                          if record['model'] == 'home.tbbestiario'
                          and record['pk'] == pk)
            self.assertEqual(fields['slug'], slug)
            self.assertEqual(fields['companheiro_subclasse'], subclass)
            self.assertIsNone(fields['nd'])
            sb = fields['statblock_json']
            self.assertFalse(is_statblock_placeholder(sb))
            self.assertEqual(sb['trait'][0]['name'], trait)
            for phrase in required:
                self.assertIn(phrase, sb['trait'][0]['entries'][0])
            creature = TbBestiario(nome=fields['nome'], slug=slug,
                                   tipo=fields['tipo'], tamanho=fields['tamanho'],
                                   ca=fields['ca'], pv=fields['pv'],
                                   statblock_json=sb)
            rendered = _render_creature_statblock_full(creature)
            self.assertIn(trait, rendered)
            self.assertNotIn('Statblock incompleto:', rendered)

        object_fields = next(record['fields'] for record in records
                             if record['model'] == 'home.tbbestiario'
                             and record['pk'] == 23)
        self.assertEqual(object_fields['ca'], 'valor de Inteligência do Mago')
        self.assertEqual(object_fields['pv'], 'nível de Mago')
        stone_fields = next(record['fields'] for record in records
                            if record['model'] == 'home.tbbestiario'
                            and record['pk'] == 25)
        self.assertEqual(size_keys(stone_fields['tamanho']), ('T',))

    def test_spectral_weapon_keeps_war_domain_rules_without_invented_stats(self):
        # Source: ref/Classes Reworkadas/Clerigo ... World Anvil.html,
        # Dominio da Guerra, Armamento da Guerra: Falange Espiritual.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario' and record['pk'] == 16)
        self.assertEqual(fields['slug'], 'arma-espectral')
        self.assertEqual(fields['companheiro_subclasse'], 122)
        self.assertTrue(fields['escala_com_dono'])
        self.assertIsNone(fields['tamanho'])
        self.assertIsNone(fields['nd'])
        self.assertIsNone(fields['ca'])
        self.assertIsNone(fields['pv'])
        statblock = fields['statblock_json']
        self.assertFalse(is_statblock_placeholder(statblock))
        rule = statblock['trait'][0]['entries'][0]
        for phrase in ('Falange Espiritual.', 'Comandar a Falange.',
                       'Limites e Propriedades.', '18 metros', '6 metros',
                       '36 metros', '1 minuto'):
            self.assertIn(phrase, rule)
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], statblock_json=statblock)
        rendered = _render_creature_statblock_full(creature)
        self.assertIn('Falange Espiritual', rendered)
        self.assertIn('Comandar a Falange', rendered)
        self.assertNotIn('Statblock incompleto:', rendered)

    def test_primal_familiar_renders_all_four_source_forms(self):
        # Source: ref/Classes/Druida ... World Anvil.html, Pastor Elemental.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        matching = [r for r in records if r['model'] == 'home.tbbestiario'
                    and r['pk'] == 20]
        self.assertEqual(len(matching), 1)
        fields = matching[0]['fields']
        self.assertEqual(fields['slug'], 'familiar-primal')
        self.assertEqual(fields['companheiro_subclasse'], 26)
        self.assertEqual(fields['tamanho'], 'S')
        self.assertEqual(fields['ca'], '11 + BP (Armadura Natural)')
        self.assertEqual(fields['pv'], '20 + 5 vezes o seu nível de Druida')
        self.assertIsNone(fields['nd'])
        sb = fields['statblock_json']
        forms = sb['forms']
        self.assertEqual([form['name'] for form in forms], [
            'Fera da Maré Guardiã', 'Fera do Sussurro do Vento',
            'Fera do Fogo Selvagem', 'Fera da Casca Ancestral',
        ])
        for form in forms:
            self.assertEqual(form['size'], 'S')
            self.assertEqual(form['type'], 'elemental')
            self.assertEqual(form['abilities'], {
                'str': 12, 'dex': 14, 'con': 14,
                'int': 13, 'wis': 17, 'cha': 10,
            })
            self.assertEqual(len(form['action']), 3)
            self.assertFalse(is_statblock_placeholder(form))
        self.assertFalse(is_statblock_placeholder(sb))
        self.assertTrue(is_statblock_placeholder({**sb, 'forms': forms[:-1] + [{}]}))
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], tamanho=fields['tamanho'],
                               ca=fields['ca'], pv=fields['pv'], statblock_json=sb)
        html = _render_creature_statblock_full(creature)
        for name in [form['name'] for form in forms]:
            self.assertIn(name, html)
        self.assertEqual(html.count('class="bonfire-creature-form"'), 4)
        self.assertIn('Refluxo Gelado', html)
        self.assertIn('Salto Ígneo', html)
        self.assertIn('Seiva de Rocha', html)
        self.assertNotIn('Statblock incompleto:', html)

    def test_shadow_monk_clone_keeps_owner_scaled_rules_without_fixed_stats(self):
        # Source: ref/Classes Reworkadas/Monge ... World Anvil.html,
        # Sombras, level 17: Duplicata das Sombras.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        matching = [r for r in records if r['model'] == 'home.tbbestiario'
                    and r['pk'] == 17]
        self.assertEqual(len(matching), 1)
        fields = matching[0]['fields']
        self.assertEqual(fields['slug'], 'clone-das-sombras')
        self.assertEqual(fields['companheiro_subclasse'], 149)
        self.assertTrue(fields['escala_com_dono'])
        self.assertIsNone(fields['nd'])
        self.assertIsNone(fields['ca'])
        self.assertIsNone(fields['tamanho'])
        self.assertEqual(fields['pv'], 'Metade dos PV do Monge')
        self.assertIn('hp:=rounddown(self.hp/2)', fields['tags_json'])
        sb = fields['statblock_json']
        self.assertEqual(sb['trait'][0]['name'], 'Duplicata das Sombras')
        rules = sb['trait'][0]['entries'][0]
        for text in ('3 Pontos de Ki', 'no máximo 3 clones', '1 hora',
                     'metade dos seus', 'Ataque Extra', '36 metros',
                     'Passo das Sombras'):
            self.assertIn(text, rules)
        self.assertFalse(is_statblock_placeholder(sb))
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], tamanho=fields['tamanho'],
                               ca=fields['ca'], pv=fields['pv'], statblock_json=sb)
        html = _render_creature_statblock_full(creature)
        self.assertIn('Duplicata das Sombras', html)
        self.assertIn('3 Pontos de Ki', html)
        self.assertNotIn('Statblock incompleto:', html)

    def test_shadow_knight_summon_preserves_variable_type_and_source_rules(self):
        # Source: ref/Classes Reworkadas/Guerreiro ... World Anvil.html,
        # Cavaleiro das Sombras, level 3: Invocar Sombra.
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        matching = [r for r in records if r['model'] == 'home.tbbestiario'
                    and r['pk'] == 26]
        self.assertEqual(len(matching), 1)
        fields = matching[0]['fields']
        self.assertEqual(fields['slug'], 'sombra')
        self.assertEqual(fields['companheiro_subclasse'], 36)
        self.assertEqual(fields['tipo'], 'tipo escolhido pelo Guerreiro')
        self.assertEqual(type_keys(fields['tipo']), ())
        self.assertIsNone(fields['tamanho'])
        self.assertEqual(fields['nd'], '0')
        self.assertEqual(fields['ca'], '14 + Bônus de Proficiência')
        self.assertEqual(fields['pv'], '1')
        sb = fields['statblock_json']
        self.assertEqual(sb['condition_immunities'], 'Todas as condições')
        self.assertEqual(sb['trait'][0]['name'], 'Invocar Sombra')
        text = ' '.join(sb['trait'][0]['entries'])
        for rule in ('4,5 metros', '9 metros', '6º nível', '18º nível',
                     'teste de resistência', 'Instável'):
            self.assertIn(rule, text)
        self.assertFalse(is_statblock_placeholder(sb))
        creature = TbBestiario(nome=fields['nome'], slug=fields['slug'],
                               tipo=fields['tipo'], tamanho=fields['tamanho'],
                               nd=fields['nd'], ca=fields['ca'], pv=fields['pv'],
                               statblock_json=sb)
        rendered = _render_creature_statblock_full(creature)
        self.assertIn('Invocar Sombra', rendered)
        self.assertIn('14 + Bônus de Proficiência', rendered)
        self.assertNotIn('Statblock incompleto:', rendered)

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


class PrimalFamiliarPreviewTests(TestCase):
    def test_source_backed_summons_show_rules_in_both_previews(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, phrase in ((40, 'Dilacerar'), (46, 'Passo Feérico'),
                           (49, 'Pancada')):
            fields = next(r['fields'] for r in records
                          if r['model'] == 'home.tbbestiario' and r['pk'] == pk)
            TbBestiario.objects.create(
                nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
                tamanho=fields['tamanho'], ca=fields['ca'], pv=fields['pv'],
                statblock_json=fields['statblock_json'],
            )
            creature = self.client.get('/api/creature/', {'slug': fields['slug']})
            self.assertEqual(creature.status_code, 200)
            self.assertFalse(creature.json()['statblock_incompleto'])
            self.assertIn(phrase, creature.json()['statblock_html'])
            card = self.client.get('/api/card-preview/', {
                'table': 'bestiario', 'args': fields['slug'],
            })
            self.assertEqual(card.status_code, 200)
            self.assertIn(phrase, card.json()['card_html'])

    def test_homunculus_servant_full_statblock_in_both_public_previews(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario'
                      and record['pk'] == 41)
        TbBestiario.objects.create(
            nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
            tamanho=fields['tamanho'], ca=fields['ca'], pv=fields['pv'],
            statblock_json=fields['statblock_json'],
        )
        creature = self.client.get('/api/creature/', {'slug': fields['slug']})
        self.assertEqual(creature.status_code, 200)
        self.assertFalse(creature.json()['statblock_incompleto'])
        card = self.client.get('/api/card-preview/', {
            'table': 'bestiario', 'args': fields['slug'],
        })
        self.assertEqual(card.status_code, 200)
        for html in (creature.json()['statblock_html'], card.json()['card_html']):
            self.assertIn('Golpe de Energia', html)
            self.assertIn('Canalizar Magia', html)
            self.assertIn('Comando do Invocador', html)

    def test_trickery_illusions_show_rules_in_both_public_previews(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, phrase in ((18, 'Onde o Golpe Erra'),
                           (22, 'Invocar Duplicidade')):
            fields = next(record['fields'] for record in records
                          if record['model'] == 'home.tbbestiario'
                          and record['pk'] == pk)
            TbBestiario.objects.create(
                nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
                statblock_json=fields['statblock_json'],
            )
            creature = self.client.get('/api/creature/', {'slug': fields['slug']})
            self.assertEqual(creature.status_code, 200)
            self.assertFalse(creature.json()['statblock_incompleto'])
            self.assertIn(phrase, creature.json()['statblock_html'])
            card = self.client.get('/api/card-preview/', {
                'table': 'bestiario', 'args': fields['slug'],
            })
            self.assertEqual(card.status_code, 200)
            self.assertIn(phrase, card.json()['card_html'])

    def test_owner_scaled_feature_objects_render_in_both_public_previews(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        for pk, phrase in ((21, 'Vínculo da Fiel Montaria'),
                           (24, 'Realidade Ilusória')):
            fields = next(record['fields'] for record in records
                          if record['model'] == 'home.tbbestiario'
                          and record['pk'] == pk)
            TbBestiario.objects.create(
                nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
                tamanho=fields['tamanho'], nd=fields['nd'], ca=fields['ca'],
                pv=fields['pv'], statblock_json=fields['statblock_json'],
            )
            creature = self.client.get('/api/creature/', {'slug': fields['slug']})
            self.assertEqual(creature.status_code, 200)
            self.assertFalse(creature.json()['statblock_incompleto'])
            self.assertIn(phrase, creature.json()['statblock_html'])
            card = self.client.get('/api/card-preview/', {
                'table': 'bestiario', 'args': fields['slug'],
            })
            self.assertEqual(card.status_code, 200)
            self.assertIn(phrase, card.json()['card_html'])

    def test_otherworldly_steed_previews_render_mechanics(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario' and record['pk'] == 39)
        TbBestiario.objects.create(
            nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
            tamanho=fields['tamanho'], nd=fields['nd'], ca=fields['ca'],
            pv=fields['pv'], statblock_json=fields['statblock_json'],
        )
        creature = self.client.get('/api/creature/', {'slug': fields['slug']})
        self.assertEqual(creature.status_code, 200)
        self.assertTrue(creature.json()['success'])
        self.assertFalse(creature.json()['statblock_incompleto'])
        card = self.client.get('/api/card-preview/', {
            'table': 'bestiario', 'args': fields['slug'],
        })
        self.assertEqual(card.status_code, 200)
        self.assertTrue(card.json()['success'])
        for html in (creature.json()['statblock_html'], card.json()['card_html']):
            for phrase in ('Golpe de Outro Mundo', 'Olhar Aterrador',
                           'Passo Feérico', 'Toque Curativo'):
                self.assertIn(phrase, html)
            self.assertNotIn('Statblock incompleto:', html)

    def test_both_public_previews_render_all_four_forms(self):
        records = json.loads((Path(settings.BASE_DIR) / 'home' / 'fixtures' /
                              'conteudo.json').read_text(encoding='utf-8'))
        fields = next(record['fields'] for record in records
                      if record['model'] == 'home.tbbestiario' and record['pk'] == 20)
        TbBestiario.objects.create(
            nome=fields['nome'], slug=fields['slug'], tipo=fields['tipo'],
            tamanho=fields['tamanho'], ca=fields['ca'], pv=fields['pv'],
            statblock_json=fields['statblock_json'],
        )
        creature = self.client.get('/api/creature/', {'slug': fields['slug']})
        self.assertEqual(creature.status_code, 200)
        creature_data = creature.json()
        self.assertTrue(creature_data['success'])
        self.assertFalse(creature_data['statblock_incompleto'])

        card = self.client.get('/api/card-preview/', {
            'table': 'bestiario', 'args': fields['slug'],
        })
        self.assertEqual(card.status_code, 200)
        card_data = card.json()
        self.assertTrue(card_data['success'])
        for html in (creature_data['statblock_html'], card_data['card_html']):
            self.assertEqual(html.count('class="bonfire-creature-form"'), 4)
            for form in fields['statblock_json']['forms']:
                self.assertIn(form['name'], html)
