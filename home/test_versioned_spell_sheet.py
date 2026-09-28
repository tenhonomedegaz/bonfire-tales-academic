from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.models import TbMagia, TbRecursoclasse
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
from home.versioned_spells import snapshot_spells
from home.versioned_library import snapshot_library
from home.versioned_conditions import snapshot_conditions
from home.tag_engine.library import Library
from home.character_engine import derive
from home.views import _magias_sheet_info


class VersionedSpellSheetTests(TestCase):
    def test_complete_sheet_preserves_catalog_and_live_preparation(self):
        Fixtures.setUp(self)
        self.cl.tags_json = ['spellcasting{ability:int, list:pinned-derive, slots:full, mode:prepared, spell_limit{fixed:3}}']
        self.cl.save()
        self.spell.classes = self.cl.nome
        self.spell.save()
        virtual = TbMagia.objects.create(nome='Virtual spell', slug='virtual-spell', nivel=1, classes=self.cl.nome, descricao='Old description')
        slots = TbRecursoclasse.objects.create(id_classe=self.cl, nome='First', slug='1o', tipo='table-only', valores_json={'1':'2'})
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_mundane_items(),
            snapshot_spells(), snapshot_conditions(), snapshot_library(raw=Library(prefer_db=False).raw)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        def read(pinned=None):
            result = _magias_sheet_info(self.person, derive(self.person, ruleset=pinned), [], ruleset=pinned)
            # Command nonces are intentionally fresh for every rendering.
            for row in result['slots']:
                row.pop('gastar_operation_id')
                row.pop('desfazer_operation_id')
            return result
        before = read(ruleset)
        self.assertEqual(before, read())
        self.assertEqual(before['total'], 2)
        self.assertTrue(any(row['catalog_only'] for row in before['lista']))
        self.cl.nome = 'Changed class'
        self.cl.tags_json = []
        self.cl.save()
        for spell in (self.spell, virtual):
            spell.slug = 'changed-' + spell.slug
            spell.descricao = 'Changed description'
            spell.classes = ''
            spell.save()
        slots.valores_json = {'1':'99'}
        slots.save()
        self.assertEqual(read(ruleset), before)
        self.choice.preparada = False
        self.choice.save()
        after = read(ruleset)
        self.assertFalse(next(row for row in after['lista'] if not row['catalog_only'])['preparada'])

    def test_pact_signature_and_workshop_keep_revision_and_live_resources(self):
        from home.models import TbPersonagemMagiaAssinatura, TbPersonagemRecurso
        from home.magic_workshop import character_casters
        Fixtures.setUp(self)
        self.cl.tags_json = ['spellcasting{ability:cha, slots{progression:pact, resource:pact_points}, list:pinned-derive, mode:known, spell_level_limit{resource:pact_cycle}}']
        self.cl.save()
        points = TbRecursoclasse.objects.create(id_classe=self.cl, nome='Pact points',
            slug='pact_points', tipo='consumable', valores_json={'1':'2', '3':'4'})
        cycle = TbRecursoclasse.objects.create(id_classe=self.cl, nome='Pact cycle',
            slug='pact_cycle', tipo='table-only', valores_json={'1':'1', '3':'2'})
        signature = TbPersonagemMagiaAssinatura.objects.create(
            id_personagem=self.person, id_magia_personagem=self.choice,
            id_magia_base=self.spell, id_classe=self.cl, slot=1, nome='My signature',
            nivel_base=1, nivel_final=1, modificacoes_json={'bonus_action':True})
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_mundane_items(),
            snapshot_spells(), snapshot_conditions(), snapshot_library(raw=Library(prefer_db=False).raw)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        def read(pinned=None):
            return _magias_sheet_info(self.person, derive(self.person, ruleset=pinned), [], ruleset=pinned)
        before = read(ruleset)
        self.assertEqual(before, read())
        resource = before['spellcasting']['mystic_resource']
        self.assertEqual(resource['maximo'], 2)
        self.assertEqual(before['spellcasting']['max_cycle'], 1)
        self.assertEqual(before['lista'][0]['magia_base_nome'], 'Old spell')
        cache = {}
        character_casters(self.person, contract_cache=cache)
        pinned = character_casters(self.person, contract_cache=cache, ruleset=ruleset)[0]
        self.assertEqual(pinned['contract']['lista_nomes'], ['Old class'])
        self.cl.nome = 'Changed class'
        self.cl.tags_json = []
        self.cl.save()
        self.spell.nome = 'Changed base'
        self.spell.descricao = 'Changed description'
        self.spell.save()
        points.valores_json = {'1':'99'}
        points.save()
        cycle.valores_json = {'1':'9'}
        cycle.save()
        self.assertEqual(read(ruleset), before)
        self.assertEqual(character_casters(self.person, ruleset=ruleset)[0]['contract'], pinned['contract'])
        self.pc.nivel = 3
        self.pc.save()
        after = read(ruleset)
        self.assertEqual(after['spellcasting']['mystic_resource']['maximo'], 4)
        self.assertEqual(after['spellcasting']['max_cycle'], 2)
        self.assertEqual(character_casters(self.person, contract_cache=cache, ruleset=ruleset)[0]['max_spell_level'], 2)
        signature.modificacoes_json = {}
        signature.save()
        self.assertNotEqual(read(ruleset)['lista'][0]['casting_time'], before['lista'][0]['casting_time'])
