from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.models import TbMagia, TbPersonagemMagia
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.versioned_spells import snapshot_spells
from home.views import _pendencias_magias, _lvl_aplicar_aprender_magias, _lvl_aplicar_trocar_magia


class VersionedLearningTests(TestCase):
    def test_learning_and_swap_preserve_identity_limits_and_quota(self):
        Fixtures.setUp(self)
        self.choice.delete()
        self.cl.tags_json = ['spellcasting{ability:int, list:pinned-derive, slots:full, mode:known, spell_limit{fixed:1}, swap{event:level_up,max:1}}']
        self.cl.save()
        self.spell.classes = self.cl.nome
        self.spell.save()
        other = TbMagia.objects.create(nome='Other old spell', slug='other-old', nivel=1, classes=self.cl.nome)
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.cl.nome = 'Changed class'
        self.cl.tags_json = []
        self.cl.save()
        for spell in (self.spell, other):
            spell.nome = 'Changed ' + spell.nome
            spell.slug = 'changed-' + spell.slug
            spell.nivel = 9
            spell.classes = ''
            spell.save()
        self.assertEqual(_pendencias_magias(self.person, ruleset=ruleset)['known_pend'], 1)
        self.assertEqual(_lvl_aplicar_aprender_magias(self.person,
            {'magias': ['pinned-spell', 'pinned-spell']}, ruleset=ruleset), [])
        learned = TbPersonagemMagia.objects.get(id_personagem=self.person)
        self.assertEqual((learned.id_magia_id, learned.nome, learned.nivel, learned.origem),
                         (self.spell.pk, 'Old spell', 1, 'Old class'))
        self.assertTrue(_lvl_aplicar_aprender_magias(self.person,
            {'magias': ['other-old']}, ruleset=ruleset))
        self.assertEqual(_lvl_aplicar_trocar_magia(self.person,
            {'remover': 'pinned-spell', 'adicionar': 'other-old'}, ruleset=ruleset), [])
        learned = TbPersonagemMagia.objects.get(id_personagem=self.person)
        self.assertEqual((learned.id_magia_id, learned.nome, learned.nivel), (other.pk, 'Other old spell', 1))
        self.assertTrue(_lvl_aplicar_trocar_magia(self.person,
            {'remover': 'other-old', 'adicionar': 'pinned-spell'}, ruleset=ruleset))
        self.assertEqual(_pendencias_magias(self.person, ruleset=ruleset)['swap_restantes'], 0)
