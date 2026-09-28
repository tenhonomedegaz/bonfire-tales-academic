from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.models import TbOpcaojogo, TbPersonagemEscolha, TbItemMagico, TbPersonagemItem
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
from home.versioned_spells import snapshot_spells
from home.views import _spell_transcription_options


class VersionedTranscriptionTests(TestCase):
    def test_preview_preserves_focus_scroll_and_spell_metadata(self):
        Fixtures.setUp(self)
        self.choice.delete()
        self.cl.tags_json = ['spellcasting{ability:int, list:pinned-derive, slots:full, mode:prepared, pool:spellbook, acquire{transcribe{source:spell_scroll,cost_po:50*spell_level,time_hours:2*spell_level}}}']
        self.cl.save()
        self.spell.escola = 'evocacao'
        self.spell.classes = self.cl.nome
        self.spell.save()
        focus = TbOpcaojogo.objects.create(nome='Focus', slug='evocacao', tipo='escola_de_foco')
        choice = TbPersonagemEscolha.objects.create(id_personagem=self.person, tipo='escola_de_foco', origem='Focus', slot=0, id_opcao=focus)
        scroll = TbItemMagico.objects.create(nome='Scroll', slug='frozen-scroll', tags_json=['spell_scroll{spell:pinned_spell, level:1}'])
        item = TbPersonagemItem.objects.create(id_personagem=self.person, nome='My scroll', id_item_magico=scroll, qtd=1)
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_mundane_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        casters = [{'pc': self.pc, 'info': {}}]
        before = _spell_transcription_options(self.person, casters, ruleset=ruleset)
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]['terms']['cost_po'], 25)
        self.assertEqual(before[0]['tempo_horas'], 1)
        focus.slug = 'other-school'
        focus.save()
        scroll.tags_json = []
        scroll.save()
        self.spell.slug = 'changed-slug'
        self.spell.nome = 'Changed name'
        self.spell.escola = 'other-school'
        self.spell.save()
        self.cl.tags_json = []
        self.cl.save()
        self.assertEqual(_spell_transcription_options(self.person, casters, ruleset=ruleset), before)
        choice.delete()
        after = _spell_transcription_options(self.person, casters, ruleset=ruleset)
        self.assertEqual(after[0]['terms']['cost_po'], 50)
        item.qtd = 0
        item.save()
        self.assertEqual(_spell_transcription_options(self.person, casters, ruleset=ruleset), [])
