"""No settings, environment files, real models or database needed for these tests."""
from copy import deepcopy
from types import ModuleType, SimpleNamespace as Obj
import unittest
from unittest.mock import MagicMock, Mock, patch

from home import vtt_spell_access as access


CURRENT = {'tipo': 'atual', 'identidade': 'spell-catalog'}


def spell(pk=1, slug='canonical-spell', level=1, tags=None):
    return Obj(pk=pk, slug=slug, nome='Catalog spell %s' % pk, nivel=level,
               tags_json=['cast{action}'] if tags is None else tags)


def owned(pk=10, spell_pk=1, prepared=False, always=False, origin='Class source'):
    return {'id': pk, 'id_magia_id': spell_pk, 'preparada': prepared,
            'sempre_preparada': always, 'origem': origin}


def grant(slug='canonical-spell', level=1, source='Active subclass', **extra):
    return {'slug': slug, 'nivel': level, 'fonte': source, **extra}


def ruleset(pk=7):
    return Obj(pk=pk, checksum='a' * 64, manifest={'spell-catalog': 'b' * 64})


class SpellAccessProjectionTests(unittest.TestCase):
    def project(self, rows=(), grants=(), catalog=None):
        return access.project_spell_access(rows, grants, catalog or {1: spell()}, catalog_source=CURRENT)

    def test_union_preserves_independent_sources_without_expanding_catalog(self):
        result = self.project(
            [owned(prepared=True), owned(pk=11, origin='Other class')],
            [grant(sempre_preparada=True)], {1: spell(), 2: spell(2, 'not-owned')})
        self.assertEqual(len(result['magias']), 1)
        entry = result['magias'][0]
        self.assertEqual(entry['magia_pk'], 1)
        self.assertEqual(entry['slug'], 'canonical-spell')
        self.assertEqual(entry['circulo'], 1)
        self.assertEqual(entry['tags'], ['cast{action}'])
        self.assertTrue(entry['persistida'])
        self.assertTrue(entry['concedida'])
        self.assertTrue(entry['preparada'])
        self.assertTrue(entry['sempre_preparada'])
        self.assertEqual(len(entry['fontes']), 3)
        self.assertEqual({s['id_fonte'] for s in entry['fontes'] if s['tipo'] == 'persistida'},
                         {'TbPersonagemMagia:10', 'TbPersonagemMagia:11'})
        self.assertFalse(result['conjuracao_automatica'])
        self.assertEqual(result['avisos'], [])

    def test_unprepared_persisted_state_is_not_mistaken_for_prepared_access(self):
        entry = self.project([owned()])['magias'][0]
        self.assertFalse(entry['preparada'])
        self.assertFalse(entry['sempre_preparada'])
        self.assertFalse(entry['concedida'])

    def test_always_prepared_is_effective_without_rewriting_persisted_flag(self):
        entry = self.project([owned(prepared=False, always=True)])['magias'][0]
        self.assertTrue(entry['preparada'])
        self.assertTrue(entry['sempre_preparada'])
        self.assertFalse(entry['fontes'][0]['preparada'])

    def test_virtual_grant_requires_explicit_preparation_semantics(self):
        result = self.project(grants=[grant()])
        entry = result['magias'][0]
        self.assertFalse(entry['persistida'])
        self.assertTrue(entry['concedida'])
        self.assertIsNone(entry['preparada'])
        self.assertIsNone(entry['sempre_preparada'])
        self.assertIn('preparation semantics unavailable', ' '.join(result['avisos']))
        explicit = self.project(grants=[grant(always_prepared=True)])['magias'][0]
        self.assertTrue(explicit['sempre_preparada'])
        self.assertTrue(explicit['preparada'])
        not_always = self.project(grants=[grant(sempre_preparada=False)])['magias'][0]
        self.assertFalse(not_always['sempre_preparada'])
        self.assertIsNone(not_always['preparada'])

    def test_missing_identities_sources_or_levels_warn_instead_of_guessing(self):
        result = self.project(
            [owned(spell_pk=None), owned(pk=12, spell_pk=99)],
            [grant(source=''), grant(slug='misspelled_spell'), grant(level=2)])
        self.assertEqual(result['magias'], [])
        self.assertGreaterEqual(len(result['avisos']), 5)

    def test_persisted_row_provenance_survives_missing_named_origin(self):
        result = self.project([owned(origin=None)])
        source = result['magias'][0]['fontes'][0]
        self.assertEqual(source['id_fonte'], 'TbPersonagemMagia:10')
        self.assertIsNone(source['origem'])
        self.assertIn('no named origin', ' '.join(result['avisos']))

    def test_invalid_catalog_identity_or_ambiguous_slug_is_not_selected(self):
        for invalid in (spell(slug=''), spell(level=10), spell(level=True), spell(pk=9)):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.project([owned()], catalog={1: invalid})['magias'], [])
        collision = self.project([owned()], [grant()], {1: spell(), 2: spell(2)})
        self.assertEqual(collision['magias'], [])
        self.assertIn('ambiguous', ' '.join(collision['avisos']))

    def test_invalid_tags_are_not_replaced_by_an_invented_program(self):
        for tags in ('cast{action}', [None], ['x' * 4097]):
            with self.subTest(tags=tags):
                result = self.project([owned()], catalog={1: spell(tags=tags)})
                self.assertFalse(result['magias'][0]['tags_disponiveis'])
                self.assertNotIn('tags', result['magias'][0])
                self.assertIn('unavailable tags', ' '.join(result['avisos']))

    def test_deterministic_idempotent_projection_does_not_mutate_inputs(self):
        rows = [owned(pk=11, spell_pk=2), owned(), owned()]
        grants = [grant(source='Z', sempre_preparada=True), grant(source='A')]
        catalog = {2: spell(2, 'second'), 1: spell()}
        before = deepcopy((rows, grants, catalog))
        first = self.project(rows, grants, catalog)
        second = self.project(list(reversed(rows)), list(reversed(grants)), dict(reversed(list(catalog.items()))))
        self.assertEqual(first, second)
        self.assertEqual((rows, grants, catalog), before)
        self.assertEqual([e['magia_pk'] for e in first['magias']], [1, 2])
        first['magias'][0]['tags'].append('changed')
        first['catalogo']['tipo'] = 'changed'
        self.assertEqual(catalog[1].tags_json, ['cast{action}'])
        self.assertEqual(CURRENT['tipo'], 'atual')


class SpellAccessReadTests(unittest.TestCase):
    def test_canonical_grant_adapter_copies_always_prepared_contract_without_sync(self):
        original = {'concedidas': [grant()], 'pendentes': [{'opcoes': ['unselected']}]}
        before = deepcopy(original)
        engine = ModuleType('home.character_engine')
        engine.magias_concedidas = Mock(return_value=original)
        person, pinned = object(), ruleset()
        with patch.dict('sys.modules', {'home.character_engine': engine}):
            data = access._read_grants(person, pinned)
        engine.magias_concedidas.assert_called_once_with(person, ruleset=pinned)
        self.assertEqual(original, before)
        self.assertIsNot(data, original)
        self.assertIsNot(data['concedidas'][0], original['concedidas'][0])
        self.assertTrue(data['concedidas'][0]['sempre_preparada'])
        projected = access.project_spell_access([], data['concedidas'], {1: spell()}, catalog_source=CURRENT)
        self.assertTrue(projected['magias'][0]['preparada'])
        self.assertTrue(projected['magias'][0]['sempre_preparada'])
        self.assertEqual(projected['avisos'], [])

    def test_link_resolution_checks_both_class_bindings_and_hunter_profiles(self):
        pinned = ruleset()
        link = Obj(ruleset_id=pinned.pk, ruleset=pinned)
        self.assertIsNone(access._ruleset_from_links([], []))
        self.assertIs(access._ruleset_from_links([link], []), pinned)
        self.assertIs(access._ruleset_from_links([], [link]), pinned)
        self.assertIs(access._ruleset_from_links([link], [link]), pinned)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            access._ruleset_from_links([link], [Obj(ruleset_id=8, ruleset=ruleset(8))])

    def test_pinned_adapter_uses_sealed_metadata_not_the_live_fk(self):
        pinned = ruleset()
        pinned_spell = spell(tags=['cast{pinned}'])
        sealed = ModuleType('home.versioned_spells')
        sealed.spell_catalog = Mock(return_value={1: pinned_spell})
        live = ModuleType('home.models')
        live.TbMagia = Mock()
        live.TbMagia.objects.filter.side_effect = AssertionError('Live catalog forbidden')
        with patch.dict('sys.modules', {'home.versioned_spells': sealed, 'home.models': live}), \
                patch.object(access, '_read_ruleset', return_value=pinned), \
                patch.object(access, '_read_owned', return_value=[owned(prepared=True)]), \
                patch.object(access, '_read_grants', return_value={'concedidas': [], 'pendentes': []}) as reader:
            result = access.effective_spell_access(object())
            pinned_spell.nome = 'Changed live object, not the exported copy'
        sealed.spell_catalog.assert_called_once_with(pinned)
        live.TbMagia.objects.filter.assert_not_called()
        self.assertIs(reader.call_args.args[1], pinned)
        self.assertEqual(result['magias'][0]['nome'], 'Catalog spell 1')
        self.assertEqual(result['magias'][0]['tags'], ['cast{pinned}'])
        self.assertEqual(result['catalogo'], {
            'tipo': 'fixado', 'identidade': 'spell-catalog', 'ruleset_pk': 7,
            'ruleset_checksum': 'a' * 64, 'revisao': 'b' * 64})

    def test_pinned_catalog_failure_does_not_fall_back_to_current(self):
        sealed = ModuleType('home.versioned_spells')
        sealed.spell_catalog = Mock(side_effect=ValueError('Missing pinned catalog'))
        live = ModuleType('home.models')
        live.TbMagia = Mock()
        with patch.dict('sys.modules', {'home.versioned_spells': sealed, 'home.models': live}), \
                patch.object(access, '_read_ruleset', return_value=ruleset()), \
                patch.object(access, '_read_owned', return_value=[owned()]), \
                patch.object(access, '_read_grants', return_value={'concedidas': [grant()]}):
            result = access.effective_spell_access(object())
        self.assertEqual(result['magias'], [])
        self.assertEqual(result['catalogo']['tipo'], 'fixado')
        self.assertIn('no current-catalog fallback', ' '.join(result['avisos']))
        live.TbMagia.objects.filter.assert_not_called()

    def test_conflicting_links_or_missing_provenance_fail_before_reading_spells(self):
        no_provenance = ruleset()
        no_provenance.manifest = {}
        for error, pinned in ((ValueError('Conflict'), None), (None, no_provenance)):
            with self.subTest(error=error), \
                    patch.object(access, '_read_ruleset', return_value=pinned, side_effect=error), \
                    patch.object(access, '_read_owned') as read_owned, \
                    patch.object(access, '_read_grants') as read_grants, \
                    patch.object(access, '_read_catalog') as read_catalog:
                result = access.effective_spell_access(object())
                self.assertIsNone(result['catalogo'])
                self.assertEqual(result['magias'], [])
                self.assertTrue(result['avisos'])
                read_owned.assert_not_called()
                read_grants.assert_not_called()
                read_catalog.assert_not_called()

    def test_pending_pool_options_are_not_exported_as_granted(self):
        with patch.object(access, '_read_ruleset', return_value=None), \
                patch.object(access, '_read_owned', return_value=[]), \
                patch.object(access, '_read_grants', return_value={
                    'concedidas': [], 'pendentes': [{'opcoes': ['canonical-spell']}]}), \
                patch.object(access, '_read_catalog', return_value={1: spell()}):
            result = access.effective_spell_access(object())
        self.assertEqual(result['magias'], [])
        self.assertIn('pending spell choices', ' '.join(result['avisos']))

    def test_failed_grant_reader_preserves_only_the_real_owned_rows(self):
        with patch.object(access, '_read_ruleset', return_value=None), \
                patch.object(access, '_read_owned', return_value=[owned()]), \
                patch.object(access, '_read_grants', side_effect=ValueError('broken feature')), \
                patch.object(access, '_read_catalog', return_value={1: spell(), 2: spell(2, 'pool')}):
            result = access.effective_spell_access(object())
        self.assertEqual([e['magia_pk'] for e in result['magias']], [1])
        self.assertFalse(result['magias'][0]['concedida'])
        self.assertIn('active grants unavailable', ' '.join(result['avisos']))


class SpellAccessExportMockTests(unittest.TestCase):
    def test_additive_export_retains_legacy_shape_and_copies_access_warnings(self):
        from home.management.commands import export_personagem_vtt as exporter
        person = Obj(pk=1, nome='Test', nivel=1, id_raca_id=None, id_essencia_id=None,
                     classes=MagicMock(), magias=MagicMock(), recursos=MagicMock())
        person.classes.select_related.return_value.order_by.return_value = []
        person.magias.select_related.return_value.order_by.return_value = [
            Obj(id_magia_id=8, nome='Persisted custom label', nivel=2,
                sempre_preparada=False, preparada=False)]
        person.recursos.filter.return_value.exclude.return_value.exists.return_value = False
        engine = ModuleType('home.character_engine')
        engine.derive = Mock(return_value={'nivel_total': 1, 'pv': {'maximo_calculado': 10}})
        block = access._empty(CURRENT, ['Test partial access warning.'])
        with patch.dict('sys.modules', {'home.character_engine': engine}), \
                patch.multiple(exporter, _recursos_espacos_magia=Mock(return_value=[]),
                               _recursos_dados_de_vida=Mock(return_value=[]),
                               _recursos_consumiveis_export=Mock(return_value=[]),
                               _habilidades=Mock(return_value=[])), \
                patch.object(access, 'effective_spell_access', return_value=block) as reader:
            result = exporter.exportar_personagem(person)
        reader.assert_called_once_with(person)
        self.assertEqual(result['versao_contrato'], 1)
        self.assertEqual(result['versao_menor'], 3)
        self.assertEqual(result['magias'], [{'magia_pk': 8, 'nome': 'Persisted custom label',
                                          'circulo': 2, 'origem': 'classe', 'preparada': False}])
        self.assertEqual(result['acesso_magias'], block)
        self.assertIn('Test partial access warning.', result['avisos'])
        self.assertEqual(result['derive']['movimento']['schema'], 1)


if __name__ == '__main__':
    unittest.main()
