"""Pure matching and actual generic grant-reader tests; no project DB/settings."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from home.character_engine import _grants_de_tag
from home.subclass_spell_catalog import resolve_spells, spell_grant_tag, build_tag_plan
from home.tag_engine.parser import parse_tag


class SubclassSpellCatalogTests(unittest.TestCase):
    def test_class_level_not_multiclass_total_controls_unlock(self):
        tag = spell_grant_tag('spell-test', 5)
        parse_tag(tag)
        for source_level, expected in ((3, []), (4, []), (5, [('spell-test', 2)]), (20, [('spell-test', 2)])):
            fixed, choice, _ = _grants_de_tag(tag, {}, {'spell-test':2}, 20,
                                             class_scopes={}, class_level=source_level)
            self.assertEqual(fixed, expected)
            self.assertIsNone(choice)
        self.assertEqual(_grants_de_tag(tag, {}, {'spell-test':2}, 4, class_scopes={})[0], [])

    def test_variants_missing_choice_do_not_grant_all_columns(self):
        left, right = spell_grant_tag('water-test',3), spell_grant_tag('fire-test',3)
        tag = 'match(pick:elemento){agua:{' + left + '}, fogo:{' + right + '}}'
        parse_tag(tag)
        for choices, expected in (({}, []), ({'elemento':'agua'}, [('water-test',1)]),
                                  ({'elemento':'fogo'}, [('fire-test',2)])):
            self.assertEqual(_grants_de_tag(tag, choices, {'water-test':1,'fire-test':2}, 20,
                                           class_scopes={},class_level=3)[0], expected)

    def test_expansion_of_class_list_is_not_a_grant(self):
        self.assertEqual(_grants_de_tag('modify:spellcasting{list}.add{spell:spell-test}', {},
                                       {'spell-test':1},20,class_scopes={})[0], [])

    def test_resolution_is_exact_and_does_not_mutate_catalog(self):
        manifest = {'entries':[{'english_name':"Dragon\u2019s Breath",'class_level':3}]}
        catalog = [{'id_magia':7,'nome':'Sopro','nome_ingles':"Dragon's Breath",'slug':'sopro','nivel':2}]
        before = deepcopy((manifest,catalog))
        out = resolve_spells(manifest,catalog)
        self.assertEqual(out['resolved'][0]['spell_pk'],7)
        self.assertEqual((manifest,catalog),before)
        catalog.append({**catalog[0], 'id_magia':8,'slug':'another'})
        self.assertEqual(resolve_spells(manifest,catalog)['pending'][0]['reason'],'ambiguous_identity')
        out=resolve_spells(manifest,catalog,overrides={"Dragon's Breath":{'slug':'sopro','level':2}})
        self.assertEqual(out['counts']['resolved'],1)
        catalog[0]['nivel']=3
        self.assertEqual(resolve_spells(manifest,catalog,overrides={"Dragon's Breath":{'slug':'sopro','level':2}})['pending'][0]['reason'],'override_level_conflict')

    def test_missing_and_explicit_circle_conflict_are_not_guessed(self):
        entries=[{'english_name':'Known','class_level':3,'spell_level':2},
                 {'english_name':'Missing','class_level':3,'supplied_portuguese_name':'Known'}]
        catalog=[{'id_magia':1,'nome':'Known','nome_ingles':'Known','slug':'known','nivel':1}]
        result=resolve_spells({'entries':entries},catalog)
        self.assertFalse(result['resolved'])
        self.assertEqual([row['reason'] for row in result['pending']],['spell_level_conflict','missing_identity'])

    def test_entire_resolved_package_uses_existing_tags_and_level_gates(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'docs/vtt/subclass-spells-resolution.json'
        if not path.exists():
            self.skipTest('API reconciliation artifact not supplied')
        package=json.loads(path.read_text(encoding='utf-8'))
        for row in package['resolved']:
            parse_tag(row['tag'])
            catalog={row['spell_slug']:row['catalog_level']}
            low=_grants_de_tag(row['tag'],{},catalog,20,class_level=row['class_level']-1,class_scopes={})
            high=_grants_de_tag(row['tag'],{},catalog,20,class_level=row['class_level'],class_scopes={})
            self.assertEqual(low[0],[],row)
            self.assertEqual(high[0],[(row['spell_slug'],row['catalog_level'])],row)

    def test_generated_spell_identifiers_pass_strict_api_validation(self):
        from home.tag_engine.library import Library
        from home.tag_engine.validator import ERROR, validate_tags_json
        tag = spell_grant_tag('palavra-curativa', 3)
        self.assertIn('spell_selection:palavra_curativa{', tag)
        self.assertFalse([issue for issue in validate_tags_json(
            [tag], Library(prefer_db=False)) if issue.level == ERROR])
        self.assertEqual(_grants_de_tag(tag, {}, {'palavra-curativa': 1}, 20,
                                      class_level=3)[0], [('palavra-curativa', 1)])
        root = Path(__file__).resolve().parents[1]
        package = json.loads((root / 'home/content_packages/subclass_spell_tags_20261104.json').read_text(encoding='utf-8'))
        library = Library(prefer_db=False)
        for definition in package['definitions']:
            self.assertFalse([issue for issue in validate_tags_json(
                definition['tags_json'], library) if issue.level == ERROR], definition['subclass'])

    def test_tag_plan_preserves_other_tags_and_creates_only_data_rows(self):
        resolution={'resolved':[{'class':'A','subclass':'B','class_level':3,'english_name':'Test',
                                'catalog_name':'Test','spell_slug':'test',
                                'tag':spell_grant_tag('test',3)}],'pending':[]}
        classes=[{'id_classe':7,'nome':'A','slug':'a'}]
        subs=[{'id_subclasse':8,'id_classe':7,'nome':'Branch B','slug':'branch-b'}]
        plan=build_tag_plan(resolution,classes,subs,[])
        self.assertEqual(plan['updates'][0]['action'],'create')
        self.assertIsNone(plan['updates'][0]['source_pk_advisory_only'])
        feature={'id_habilidade':91,'id_classe':7,'id_subclasse':8,'nome':'Magias de B',
                 'niveladquirido':3,'tags_json':['speed:+10'],'descricao':''}
        before=deepcopy(feature)
        plan=build_tag_plan(resolution,classes,subs,[feature])
        self.assertEqual(plan['updates'][0]['action'],'update')
        self.assertEqual(plan['updates'][0]['tags_json'][0],'speed:+10')
        self.assertEqual(feature,before)

    def test_replacement_is_exact_reviewed_data_and_repeatable(self):
        resolution = {'resolved': [{'class': 'A', 'subclass': 'B', 'class_level': 3,
            'english_name': 'Test', 'catalog_name': 'Test', 'spell_slug': 'test',
            'tag': spell_grant_tag('test', 3)}], 'pending': []}
        classes = [{'id_classe': 7, 'nome': 'A', 'slug': 'a'}]
        subclasses = [{'id_subclasse': 8, 'id_classe': 7, 'nome': 'B', 'slug': 'b'}]
        old = 'spell_selection:old{always_prepared}'
        keep = 'spell_selection:independent{always_prepared}'
        feature = {'id_habilidade': 91, 'id_classe': 7, 'id_subclasse': 8,
            'nome': 'Magias de B', 'niveladquirido': 3,
            'tags_json': [old, keep, 'speed:+10']}
        binding = {'A/B': {'replace_tags': [old]}}
        plan = build_tag_plan(resolution, classes, subclasses, [feature], bindings=binding)
        update = plan['updates'][0]
        self.assertEqual(update['removed_tags'], [old])
        self.assertEqual(update['tags_json'], [keep, 'speed:+10', spell_grant_tag('test', 3)])
        feature['tags_json'] = update['tags_json']
        repeated = build_tag_plan(resolution, classes, subclasses, [feature], bindings=binding)
        self.assertEqual(repeated['updates'][0]['tags_json'], update['tags_json'])
        self.assertEqual(repeated['updates'][0]['removed_tags'], [])
        with self.assertRaises(ValueError):
            build_tag_plan(resolution, classes, subclasses, [feature],
                           bindings={'A/B': {'replace_tags': ['speed:+10']}})

    def test_all_planned_variant_tags_are_read_by_the_same_generic_reader(self):
        root=Path(__file__).resolve().parents[1]
        package=json.loads((root/'docs/vtt/subclass-spells-tag-plan.json').read_text(encoding='utf-8'))
        catalog=json.loads((root/'docs/vtt/subclass-spells-resolution.json').read_text(encoding='utf-8'))
        levels={row['spell_slug']:row['catalog_level'] for row in catalog['resolved']}
        for update in package['updates']:
            added=[tag for tag in update['tags_json'] if tag not in update['before_tags']]
            for tag in added:
                parse_tag(tag)
                if tag.startswith('match('):
                    self.assertFalse(_grants_de_tag(tag,{},levels,20,class_scopes={},class_level=20)[0],tag)

    def test_confirmed_reference_has_no_unresolved_spell_identities(self):
        root=Path(__file__).resolve().parents[1]
        package=json.loads((root/'docs/vtt/subclass-spells-resolution.json').read_text(encoding='utf-8'))
        self.assertEqual(package['counts'],{'total':595,'resolved':595,'pending':0})
        self.assertFalse(package['pending'])
        for row in package['resolved']:
            if row['english_name'].casefold()=='branding smite':
                self.assertEqual(row['spell_slug'],'golpe-brilhante')
                self.assertEqual(row['catalog_level'],2)
            if row['english_name']=='Grave Ground':
                self.assertEqual(row['spell_slug'],'solo-sepulcral')
                self.assertEqual(row['catalog_level'],5)
        spell=json.loads((root/'home/content_packages/grave_ground_20261104.json').read_text(encoding='utf-8'))
        self.assertEqual(spell['classes_slugs'],['clerigo','mistico','mago'])
        from home.tag_engine.library import Library
        from home.tag_engine.validator import validate_tags_json
        self.assertEqual(validate_tags_json(spell['tags_json'],Library(prefer_db=False)),[])


if __name__ == '__main__':
    unittest.main()
