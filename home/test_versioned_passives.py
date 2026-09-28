from types import SimpleNamespace as NS
from unittest.mock import patch
from django.test import TestCase
from home.models import TbItemMagico, TbCondicao
from home.content_versions import seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
from home.versioned_origins import snapshot_origins
from home.versioned_conditions import snapshot_conditions
from home.versioned_library import snapshot_library
from home.tag_engine.library import Library
from home.character_engine import apply_tags, _features_de_itens


class Rows(list):
    def all(self): return self
    def select_related(self, *args): return self
    def filter(self, **kwargs): return Rows(x for x in self if all(getattr(x, k) == v for k, v in kwargs.items()))


class VersionedPassivesTests(TestCase):
    def test_passive_armor_and_immunity_preserve_catalog_and_live_equipment(self):
        magic = TbItemMagico.objects.create(nome='Pinned shield', slug='passive-shield', slot='escudo',
            tags_json=['ca:+3', 'cond_immune:envenenado'])
        condition = TbCondicao.objects.create(nome='Original poison label', slug='envenenado')
        ruleset = seal_ruleset([snapshot_magic_items(), snapshot_mundane_items(), snapshot_origins(),
            snapshot_conditions(), snapshot_library(raw=Library(prefer_db=False).raw)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        item = NS(id_item_magico_id=magic.pk, id_item_magico=magic, id_item_mundano_id=None,
                  id_item_mundano=None, nome='My shield', tags_json=[], equipado=True, sintonizado=True)
        person = NS(inventario=Rows([item]), talentos=Rows([]))
        def read(pinned=None):
            features = _features_de_itens(person, ruleset=pinned)
            state = {'_ctx': {'lvl': 2, 'classlvl': 2, 'pb': 2, 'dex_mod': 2},
                     'pv': {'maximo_calculado': 20}, 'ca': 10, 'velocidade': '30 ft', 'recursos': {}}
            return apply_tags(state, features, person, {}, ruleset=pinned)
        before = read(ruleset)
        self.assertEqual(before['ca'], 15)
        self.assertIn('Original poison label', str(before))
        magic.tags_json = ['ca:+9']
        magic.save()
        condition.nome = 'Changed label'
        condition.save()
        self.assertNotEqual(read(), before)
        with patch('home.tag_engine.library._active_database_library', side_effect=AssertionError('live vocabulary')):
            self.assertEqual(read(ruleset), before)
        item.equipado = False
        self.assertEqual(read(ruleset)['ca'], 12)
        self.assertIs(item.id_item_magico, magic)

    def test_talent_attribute_mapping_uses_pinned_slug_and_live_selection(self):
        from home.models import TbTalento
        from home.character_engine import _talent_attr_map
        talent = TbTalento.objects.create(nome='Pinned talent', slug='old-talent', descricao='')
        ruleset = seal_ruleset([snapshot_origins()], evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY)
        selection = NS(id_talento_id=talent.pk, id_talento=talent, nome=talent.nome,
                       detalhes='talent_attr:INT')
        person = NS(talentos=Rows([selection]))
        talent.slug = 'changed-talent'
        talent.save()
        result = _talent_attr_map(person, ruleset=ruleset)
        self.assertEqual(result[('slug', 'old-talent')], 'INT')
        self.assertNotIn(('slug', 'changed-talent'), result)
        selection.detalhes = 'talent_attr:SAB'
        self.assertEqual(_talent_attr_map(person, ruleset=ruleset)[('id', talent.pk)], 'SAB')
        selection.id_talento_id = 999999
        with self.assertRaisesMessage(ValueError, 'Talent attribute source absent'):
            _talent_attr_map(person, ruleset=ruleset)
