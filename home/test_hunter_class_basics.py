"""The saved Hunter reference governs new multiclass sheets; legacy rows stay pinned."""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import views
from .character_engine import derive
from .content_versions import create_revision, seal_ruleset
from .hunter_catalog import compose_class_basics_revision
from .hunter_rework import catalog
from .ranger_reference import extract_reference
from .models import TbClasse, TbPersonagem, TbPersonagemCacador, TbPersonagemClasse
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class
from .versioned_options import snapshot_options
from .versioned_origins import snapshot_origins
from .versioned_items import snapshot_magic_items, snapshot_mundane_items
from .versioned_conditions import snapshot_conditions
from .versioned_spells import snapshot_spells
from .versioned_library import snapshot_library
from .tag_engine.library import Library


class HunterClassBasicsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        from .models import TbRegra
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        cls.hunter = TbClasse.objects.get(slug='cacador')
        cls.fighter = TbClasse.objects.get(slug='guerreiro')
        cls.base = seal_ruleset([
            create_revision('hunter-rework', catalog()),
            create_revision(f'class-catalog:{cls.hunter.pk}', inventory_class(cls.hunter.pk)),
            create_revision(f'class-catalog:{cls.fighter.pk}', inventory_class(cls.fighter.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(),
            snapshot_mundane_items(), snapshot_conditions(), snapshot_spells(),
            snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        cls.published = compose_class_basics_revision(cls.base, class_id=cls.hunter.pk)
        cls.user = get_user_model().objects.create_user(username='hunter-basics', password='x')

    def character(self, *, dex=13, wis=13, strength=13, intelligence=10, hunter=False):
        p = TbPersonagem.objects.create(dono=self.user, nome='Teste multiclass', nivel=1,
            aventuras=500, forca=strength, destreza=dex, constituicao=12,
            inteligencia=intelligence, sabedoria=wis, carisma=10)
        TbPersonagemClasse.objects.create(id_personagem=p,
            id_classe=self.hunter if hunter else self.fighter, nivel=1, principal=True)
        return p

    def test_new_revision_matches_html_without_mutating_legacy_catalog(self):
        reference = catalog()
        root = Path(__file__).resolve().parent.parent
        source = extract_reference(root / 'ref/Classes Reworkadas' / reference['source_file'])
        section = next(e['section_text'] for e in source['entries']
                       if e['id'] == '004-multiclasse')
        self.assertIn('13 em Destreza e em Sabedoria', section)
        self.assertIn('Armaduras Leves, Armas Marciais e uma perícia', section)
        before = VersionedClassCatalog(self.base, self.hunter.pk).classe
        after = VersionedClassCatalog(self.published, self.hunter.pk).classe
        self.assertIn('armadura_media', str(before.tags_json))
        self.assertIn('multiclass_req{dex>=13, wis>=13}', after.tags_json)
        self.assertIn('multiclass_prof{armadura_leve, armas_marciais, pick:pericia:1}',
                      after.tags_json)
        mc = next(t for t in after.tags_json if t.startswith('multiclass_prof{'))
        self.assertNotIn('armadura_media', mc)
        self.assertNotIn('escudos', mc)
        self.assertNotIn('Arcanismo', after.multiclass_pericias)
        self.assertNotIn('Religião', after.multiclass_pericias)
        self.assertEqual(compose_class_basics_revision(self.published,
                         class_id=self.hunter.pk).checksum, self.published.checksum)
        self.hunter.refresh_from_db()
        self.assertIn('armadura_media', str(self.hunter.tags_json))

    def test_new_hunter_requires_dex_wis_and_explicit_ability(self):
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.published.checksum):
            bad = self.character(dex=12, wis=12, strength=13, intelligence=13)
            self.assertNotIn(self.hunter.pk,
                {row['id'] for row in views._classes_multiclasse(bad, derive(bad))})
            self.assertTrue(views._lvl_aplicar_adicionar_classe(bad,
                {'classe': self.hunter.pk, 'hunter_ability': 'int'}))
            self.assertFalse(bad.classes.filter(id_classe=self.hunter).exists())
            good = self.character()
            self.assertIn(self.hunter.pk,
                {row['id'] for row in views._classes_multiclasse(good, derive(good))})
            self.assertTrue(views._lvl_aplicar_adicionar_classe(good,
                {'classe': self.hunter.pk}))
            self.assertFalse(good.classes.filter(id_classe=self.hunter).exists())
            self.assertEqual(views._lvl_aplicar_adicionar_classe(good,
                {'classe': self.hunter.pk, 'hunter_ability': 'wis'}), [])
            profile = TbPersonagemCacador.objects.get(personagem_classe__id_personagem=good)
            self.assertEqual((profile.ruleset_id, profile.ability, profile.selected),
                             (self.published.pk, 'wis', []))
            sheet = derive(good, ruleset=self.published)
            self.assertNotIn('Média', sheet.get('prof_multiclasse_armadura', []))
            self.assertNotIn('Escudos', sheet.get('prof_multiclasse_armadura', []))

    def test_legacy_hunter_keeps_old_prerequisites(self):
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.published.checksum):
            old = self.character(dex=12, wis=12, strength=13, intelligence=13,
                                 hunter=True)
            attrs = derive(old)['atributos']
            self.assertTrue(views._multiclass_atende_classes(old, attrs, self.fighter))
            self.assertFalse(TbPersonagemCacador.objects.filter(
                personagem_classe__id_personagem=old).exists())

    def test_levelup_preview_and_apply_bind_new_hunter_only_on_apply(self):
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.published.checksum):
            p = self.character()
            self.client.force_login(self.user)
            body = json.dumps({'acoes': [{'tipo': 'adicionar_classe', 'payload': {
                'classe': self.hunter.pk, 'hunter_ability': 'int'}}]})
            preview = self.client.post(reverse('personagem_levelup_preview', args=[p.pk]),
                data=body, content_type='application/json')
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertTrue(preview.json()['ready'], preview.content)
            self.assertFalse(p.classes.filter(id_classe=self.hunter).exists())
            applied = self.client.post(reverse('personagem_levelup_aplicar', args=[p.pk]),
                data=body, content_type='application/json')
            self.assertEqual(applied.status_code, 200, applied.content)
            self.assertTrue(applied.json()['ok'])
            self.assertEqual(p.classes.filter(id_classe=self.hunter).count(), 1)
            self.assertEqual(TbPersonagemCacador.objects.get(
                personagem_classe__id_personagem=p).ability, 'int')

    def test_levelup_page_exposes_reviewed_hunter_choice(self):
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.published.checksum):
            p = self.character()
            self.client.force_login(self.user)
            response = self.client.get(reverse('personagem_subir_nivel', args=[p.pk]))
            self.assertEqual(response.status_code, 200, response.content[:300])
            html = response.content.decode('utf-8')
            self.assertIn(f'value="{self.hunter.pk}" data-hunter="1"', html)
            self.assertIn('dex&gt;=13, wis&gt;=13', html)
            self.assertIn('data-hunter-choice hidden', html)
            self.assertIn('data-lvl-field="hunter_ability"', html)
