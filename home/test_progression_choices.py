"""Milestone grant regression: threshold, tags, rollback and duplicate requests."""
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import RequestFactory, override_settings
from django.urls import reverse

from home import progression_choices as milestones, views
from home.character_engine import derive
from home.epic_talent_catalog import epic_candidates
from home.models import TbOpcaojogo, TbPersonagemTalento, TbPersonagemAtributoBonus
from home.test_criador import _CriadorBase


@override_settings(TEMPLATES=[{
    'BACKEND':'django.template.backends.django.DjangoTemplates', 'APP_DIRS':True,
    'OPTIONS':{'libraries':{'humanize':'django.contrib.humanize.templatetags.humanize'},
               'context_processors':['django.template.context_processors.request',
                                     'django.contrib.auth.context_processors.auth']},
}])
class ProgressionChoiceTests(_CriadorBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        migration = importlib.import_module('home.migrations.0162_progression_milestone_choice')
        migration.seed_policy(apps, SimpleNamespace(connection=connection))
        from home.models import TbTalento
        for values in epic_candidates():
            values = dict(values)
            TbTalento.objects.update_or_create(slug=values.pop('slug'), defaults=values)

    def character(self, adventures=160, level=20):
        user = self._novo_usuario('milestone-owner')
        payload = self._payload('guerreiro')
        resolved, errors = views._criador_public_resolution(payload)
        self.assertFalse(errors)
        p = views._criador_persistir(user, payload, resolved)
        pc = p.classes.first()
        pc.nivel = level
        pc.save(update_fields=['nivel'])
        p.nivel, p.aventuras = level, adventures
        p.save(update_fields=['nivel', 'aventuras'])
        return p

    def payload(self, slug='dadiva-da-fortitude', attr='DES'):
        from home.models import TbTalento
        return {'marco':'progressao-epic-boon', 'talento':str(TbTalento.objects.get(slug=slug).pk),
                'talento_attr':attr}

    def request(self, p, endpoint, actions):
        request = RequestFactory().post(reverse(endpoint, args=[p.pk]),
            data=json.dumps({'acoes': actions}), content_type='application/json')
        request.user = p.dono
        return getattr(views, endpoint)(request, pk=p.pk)

    def test_threshold_and_no_class_level_21(self):
        p = self.character(159)
        self.assertFalse(milestones.pending(p))
        views.aplicar_aventuras(p, 1)
        self.assertEqual([m['slug'] for m in milestones.pending(p)], ['progressao-epic-boon'])
        self.assertEqual(derive(p)['progressao']['nivel_label'], 'Epic Boon')
        self.assertEqual(p.nivel, 20)
        p.nivel = 19
        self.assertFalse(milestones.pending(p))

    def test_catalog_is_epic_only_and_tags_derive_once(self):
        p = self.character()
        available = milestones.pending(p)[0]['talentos']
        self.assertTrue(available)
        from home.models import TbTalento
        self.assertEqual(set(TbTalento.objects.filter(pk__in=[t['id'] for t in available])
                             .values_list('tipo', flat=True)), {'epico'})
        before = derive(p)
        asi_before = views._pendencias_nivel(p)['asi_pendentes']
        self.assertFalse(milestones.apply_choice(p, self.payload()))
        after = derive(p)
        self.assertEqual(after['atributos']['DES']['valor'], before['atributos']['DES']['valor'] + 2)
        self.assertEqual(after['pv']['maximo_calculado'], before['pv']['maximo_calculado'] + 40)
        self.assertEqual(views._pendencias_nivel(p)['asi_pendentes'], asi_before)
        self.assertFalse(TbPersonagemAtributoBonus.objects.filter(id_personagem=p, origem_tipo='talento-asi').exists())
        self.assertFalse(milestones.pending(p))
        self.assertTrue(milestones.apply_choice(p, self.payload()))
        self.assertEqual(p.talentos.filter(categoria='epico').count(), 1)
        self.assertEqual(derive(p)['pv']['maximo_calculado'], after['pv']['maximo_calculado'])
        views.aplicar_aventuras(p, 40)
        self.assertEqual(derive(p)['progressao']['nivel_label'], 'Lenda')
        self.assertFalse(milestones.pending(p))

    def test_invalid_selection_and_premature_requests_do_not_persist(self):
        p = self.character(159)
        count = p.talentos.count()
        self.assertTrue(milestones.apply_choice(p, self.payload()))
        views.aplicar_aventuras(p, 1)
        self.assertTrue(milestones.apply_choice(p, self.payload(attr='INVALID')))
        from home.models import TbTalento
        general = TbTalento.objects.filter(tipo='geral').first()
        data = self.payload()
        data['talento'] = str(general.pk)
        self.assertTrue(milestones.apply_choice(p, data))
        self.assertEqual(p.talentos.count(), count)

    def test_preview_rolls_back_apply_persists_and_replay_is_rejected(self):
        p = self.character()
        action = {'tipo':'marco', 'payload':self.payload()}
        response = self.request(p, 'personagem_levelup_preview', [action])
        preview = json.loads(response.content)
        self.assertTrue(preview['ready'], preview)
        self.assertFalse(preview['erros'], preview)
        self.assertFalse(preview['pendencias']['marcos_pendentes'])
        self.assertFalse(p.talentos.filter(categoria='epico').exists())
        response = self.request(p, 'personagem_levelup_aplicar', [action])
        self.assertEqual(response.status_code, 200, response.content)
        response = self.request(p, 'personagem_levelup_aplicar', [action])
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(p.talentos.filter(categoria='epico').count(), 1)

    def test_mixed_invalid_batch_rolls_back_grant(self):
        p = self.character()
        response = self.request(p, 'personagem_levelup_aplicar', [
            {'tipo':'marco', 'payload':self.payload()}, {'tipo':'unknown', 'payload':{}}])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(p.talentos.filter(categoria='epico').exists())
        self.assertTrue(milestones.pending(p))

    def test_milestone_metadata_is_editable_and_seed_preserves_policy(self):
        p = self.character()
        policy = TbOpcaojogo.objects.get(slug='progressao-epic-boon')
        policy.tags_json = ['progression{adventures:170,level:20}', 'pick:talento:1(tipo:epico)']
        policy.save(update_fields=['tags_json'])
        importlib.import_module('home.migrations.0162_progression_milestone_choice').seed_policy(
            apps, SimpleNamespace(connection=connection))
        self.assertFalse(milestones.pending(p))
        views.aplicar_aventuras(p, 10)
        self.assertTrue(milestones.pending(p))

    def test_attribute_cap_is_from_tags(self):
        p = self.character()
        p.destreza = 29
        p.save(update_fields=['destreza'])
        # Background adds one DES: the grant must not exceed the tag cap.
        self.assertFalse(milestones.apply_choice(p, self.payload()))
        self.assertEqual(derive(p)['atributos']['DES']['valor'], 30)

    def test_nested_choices_are_required(self):
        p = self.character()
        from home.models import TbTalento
        talent = TbTalento.objects.get(slug='dadiva-da-fortitude')
        talent.tags_json = list(talent.tags_json) + ['pick:pericia:1']
        talent.save(update_fields=['tags_json'])
        self.assertTrue(milestones.apply_choice(p, self.payload()))
        self.assertFalse(p.talentos.filter(id_talento=talent).exists())

    def test_page_offers_milestone_choice(self):
        p = self.character()
        request = RequestFactory().get(reverse('personagem_subir_nivel', args=[p.pk]))
        request.user = p.dono
        response = views.personagem_subir_nivel(request, pk=p.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-lvl-card="marco"')
        self.assertContains(response, 'Epic Boon')
        self.assertContains(response, 'Talento de Epic Boon')

    def test_existing_manual_epic_grant_is_not_duplicated(self):
        p = self.character()
        from home.models import TbTalento
        talent = TbTalento.objects.get(slug='dadiva-da-fortitude')
        TbPersonagemTalento.objects.create(id_personagem=p, id_talento=talent,
            nome=talent.nome, categoria='epico', nivel=21, detalhes='talent_attr:DES')
        self.assertFalse(milestones.pending(p))
        self.assertTrue(milestones.apply_choice(p, self.payload()))
        self.assertEqual(p.talentos.filter(categoria='epico').count(), 1)

    def test_global_grant_is_available_with_older_class_snapshot(self):
        p = self.character()
        self.assertFalse(milestones.apply_choice(p, self.payload()))
        from home.versioned_origins import VersionedOrigins
        from home.character_engine import _talent_attr_map
        from home.models import TbTalento
        catalog = object.__new__(VersionedOrigins)
        current = list(TbTalento.objects.exclude(tipo='epico'))
        catalog.objects = lambda model: current if model is TbTalento else []
        # The selected new global talent is absent from the older sealed catalog.
        with patch('home.versioned_origins.VersionedOrigins', return_value=catalog):
            mapping = _talent_attr_map(p, ruleset=object())
        owned = p.talentos.get(categoria='epico')
        self.assertEqual(mapping[('id', owned.id_talento_id)], 'DES')
        self.assertTrue(any(feature.pk == owned.id_talento_id
                            for kind, category, feature, _ in catalog.talents(p)
                            if kind == 'talento'))
