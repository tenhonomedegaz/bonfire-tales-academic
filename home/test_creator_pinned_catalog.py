from unittest.mock import patch
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
import json

from . import views
from .test_criador import _CriadorBase
from .models import (TbClasse, TbClassehabilidade, TbRaca, TbTracoracial,
                     TbAntecedente, TbPersonagem, TbPersonagemMagia)
from .content_versions import create_revision, seal_ruleset
from .versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from .versioned_origins import snapshot_origins
from .versioned_spells import snapshot_spells
from .versioned_options import snapshot_options
from .versioned_items import snapshot_mundane_items, snapshot_magic_items
from .versioned_conditions import snapshot_conditions
from .versioned_library import snapshot_library
from .tag_engine.library import Library


class CreatorPinnedCatalogTests(_CriadorBase):
    def seal(self, classe):
        return seal_ruleset([
            create_revision('class-catalog:%s' % classe.pk, inventory_class(classe.pk)),
            snapshot_origins(), snapshot_spells(), snapshot_options(),
            snapshot_mundane_items(), snapshot_magic_items(), snapshot_conditions(),
            snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def test_create_and_preview_share_frozen_class_and_race(self):
        payload = self._payload('guerreiro', raca_slug='humano')
        classe = TbClasse.objects.get(slug='guerreiro')
        ruleset = self.seal(classe)
        resolver = views._criador_resolver
        resolved, errors = resolver(payload, ruleset=ruleset, class_id=classe.pk)
        self.assertEqual(errors, [])
        user = self._novo_usuario('pinned-creator')
        self.client.force_login(user)
        def pinned(data):
            return resolver(data, ruleset=ruleset, class_id=classe.pk)
        with patch('home.views._criador_resolver', side_effect=pinned):
            before = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(payload), content_type='application/json').json()
            self.assertTrue(before['ready'], before)
            self.assertEqual(before['erros'], [])
            self.assertFalse(TbPersonagem.objects.exists())
            TbClasse.objects.filter(pk=classe.pk).update(nome='Changed class', tags_json=[], dado_vida='d4')
            TbClassehabilidade.objects.filter(id_classe=classe).update(tags_json=[])
            TbRaca.objects.filter(slug='humano').update(nome='Changed race', permite_essencia=False)
            TbTracoracial.objects.all().update(nome='Changed trait', tags_json=[])
            TbAntecedente.objects.all().update(tags_json=[])
            after = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(payload), content_type='application/json').json()
            self.assertEqual(after, before)
            response = self._post_criar(user, payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.pv_maximo, before['preview']['pv'])
        self.assertEqual(person.ca, before['preview']['ca'])
        self.assertEqual(person.talentos.get(categoria='origem').nome, resolved['to'].nome)
        self.assertFalse(person.talentos.filter(categoria='racial').exists())
        for trait in resolved['racial_sources']:
            if any('pick:ferramenta' in str(t) for t in trait.tags_json):
                self.assertTrue(person.escolhas.filter(origem=trait.nome, tipo='ferramenta').exists())
        _, live_errors = resolver(payload)
        self.assertTrue(live_errors)

    def test_missing_catalog_or_class_identity_does_not_fallback(self):
        payload = self._payload('guerreiro')
        classe = TbClasse.objects.get(slug='guerreiro')
        incomplete = seal_ruleset([
            create_revision('class-catalog:%s' % classe.pk, inventory_class(classe.pk)),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(ObjectDoesNotExist):
            views._criador_resolver(payload, ruleset=incomplete, class_id=classe.pk)
        ruleset = self.seal(classe)
        with self.assertRaisesMessage(ValueError, 'explicit class identity'):
            views._criador_resolver(payload, ruleset=ruleset)
        payload['classe'] = 'mago'
        with self.assertRaisesMessage(ValueError, 'Class differs'):
            views._criador_resolver(payload, ruleset=ruleset, class_id=classe.pk)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_essence_choices_and_racial_talents_use_frozen_sources(self):
        from .models import TbEssencia
        payload = self._payload('feiticeiro', essencia_slug='draconica', vertente='Vermelho',
            escolhas_raca={'menus': [{'tipo': 'alento_elemental',
                'fonte': 'Alento Elemental', 'valores': ['fogo']}]})
        classe = TbClasse.objects.get(slug='feiticeiro')
        ruleset = self.seal(classe)
        before, errors = views._criador_resolver(payload, ruleset=ruleset, class_id=classe.pk)
        self.assertEqual(errors, [])
        TbEssencia.objects.all().update(tags_json=[])
        TbTracoracial.objects.all().update(nome='Changed', tags_json=[], descricao='', pre_requisito='')
        after, errors = views._criador_resolver(payload, ruleset=ruleset, class_id=classe.pk)
        self.assertEqual(errors, [])
        self.assertEqual(after['talento_racial_nome'], before['talento_racial_nome'])
        self.assertEqual(after['generic_picks'], before['generic_picks'])
        payload['escolhas_raca']['menus'][0]['valores'] = ['invalid']
        _, errors = views._criador_resolver(payload, ruleset=ruleset, class_id=classe.pk)
        self.assertIn('Alento Elemental', ' '.join(errors))
