from types import SimpleNamespace as NS
from django.test import TestCase
from home.models import TbClasse, TbRecursoclasse
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_spells import snapshot_spells
from home.views import _spell_slot_totals


class VersionedSlotTotalsTests(TestCase):
    def test_multiclass_discovers_only_frozen_full_table_and_tracks_levels(self):
        full = TbClasse.objects.create(nome='Full', slug='full-slots',
            tags_json=['spellcasting{ability:int, list:full-slots, slots:full}'])
        half = TbClasse.objects.create(nome='Half', slug='half-slots')
        third = TbClasse.objects.create(nome='Third', slug='third-slots')
        table = TbRecursoclasse.objects.create(id_classe=full, nome='First circle',
            slug='1o', tipo='table-only', valores_json={'1':'2','3':'4','4':'5'})
        ruleset = seal_ruleset([create_revision('class-catalog:%s' % c.pk, inventory_class(c.pk))
            for c in (full,half,third)] + [snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        casters = [
            {'pc': NS(id_classe=half, nivel=4, id_subclasse=None), 'info': {'slots':'half'}},
            {'pc': NS(id_classe=third, nivel=3, id_subclasse=None), 'info': {'slots':'third'}}]
        self.assertEqual(_spell_slot_totals(casters, ruleset=ruleset), {1:4})
        table.valores_json = {'1':'99'}
        table.save()
        full.tags_json = []
        full.save()
        self.assertEqual(_spell_slot_totals(casters, ruleset=ruleset), {1:4})
        casters[1]['pc'].nivel = 6
        self.assertEqual(_spell_slot_totals(casters, ruleset=ruleset), {1:5})
        table.delete()
        self.assertEqual(_spell_slot_totals(casters, ruleset=ruleset), {1:5})
