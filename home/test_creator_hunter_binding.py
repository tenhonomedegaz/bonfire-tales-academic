import json
from unittest.mock import patch
from django.test import override_settings
from django.db import transaction
from django.urls import reverse
from . import views
from .test_creator_pinned_catalog import CreatorPinnedCatalogTests
from .test_criador import _CriadorBase
from .models import TbClasse, TbPersonagem, TbPersonagemCacador, TbMagia
from .content_versions import create_revision, seal_ruleset
from .versioned_classes import EVALUATOR, VOCABULARY
from .hunter_rework import catalog


class CreatorHunterBindingTests(_CriadorBase):
    def setup_creation(self):
        self.classe = TbClasse.objects.get(slug='cacador')
        self.classe.tags_json = [t for t in self.classe.tags_json if 'spellcasting' not in str(t)] + [
            'spellcasting{ability:wis, list:cacador, slots:half, mode:prepared, spell_limit{formula:classlvl+spell_mod}}']
        self.classe.save()
        if not TbMagia.objects.filter(nome_ingles="Hunter's Mark").exists():
            TbMagia.objects.create(nome='Marca congelada', nome_ingles="Hunter's Mark", slug='mark-test', nivel=1)
        # Explicit test catalog: the imported legacy fixture lacks Hunter access.
        from .models import TbOpcaojogo, TbAcessoopcao
        style = TbOpcaojogo.objects.create(nome='Test Hunter style', slug='test-hunter-style',
            tipo='Estilo de Luta', tags_json=[])
        TbAcessoopcao.objects.create(id_opcao=style, id_classe=self.classe, nivel_recebimento=1)
        base = CreatorPinnedCatalogTests.seal(self, self.classe)
        self.ruleset = seal_ruleset([e.revision for e in base.entries.select_related('revision')] + [
            create_revision('hunter-rework', catalog())],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.user = self._novo_usuario('hunter-creator', staff=True)
        self.payload = self._payload('cacador')
        self.payload['hunter_ability'] = 'int'
        self.payload['estilo_luta'] = style.slug
        resolver = views._criador_resolver
        self.resolve = lambda data: resolver(data, ruleset=self.ruleset, class_id=self.classe.pk)

    def valid_payload(self, ability):
        self.payload['hunter_ability'] = ability
        result, _ = self.resolve(self.payload)
        conj = result['conj']
        count = views._spell_count_nv1(conj, result['base'], result['mais2'], result['mais1'],
            (result['asi_major'], result['asi_minor']), asi_bonus=result['asi_bonus'])
        self.payload['magias'] = [m['slug'] for m in conj['magias_nv1']][:count]
        return self.resolve(self.payload)

    def test_both_abilities_bind_before_grants_and_vitals_and_open_linked_sheet(self):
        self.setup_creation()
        for ability in ('int', 'wis'):
            with self.subTest(ability=ability), transaction.atomic():
                result, errors = self.valid_payload(ability)
                self.assertEqual(errors, [])
                self.assertEqual(result['conj']['ability'], ability)
                person = views._criador_persistir(self.user, self.payload, result, strict_spell_choices=True)
                profile = TbPersonagemCacador.objects.get(personagem_classe__id_personagem=person)
                self.assertEqual((profile.ruleset_id, profile.ability), (self.ruleset.pk, ability))
                self.assertTrue(person.magias.filter(id_magia__nome_ingles="Hunter's Mark", sempre_preparada=True).exists())
                self.client.force_login(self.user)
                response = self.client.get(reverse('hunter_sheet', args=[person.pk]))
                self.assertEqual(response.status_code, 200, response.content[:200])
                transaction.set_rollback(True)

    def test_invalid_choice_and_late_failure_leave_no_character_or_binding(self):
        self.setup_creation()
        for ability in (None, 'cha', '', ['int']):
            self.payload['hunter_ability'] = ability
            result, errors = self.resolve(self.payload)
            self.assertTrue(errors)
            self.assertIsNone(result['hunter_creation'])
        result, errors = self.valid_payload('int')
        self.assertEqual(errors, [])
        with self.assertRaises(RuntimeError), transaction.atomic():
            with patch('home.views._refresh_vitais_derivados', side_effect=RuntimeError('late failure')):
                views._criador_persistir(self.user, self.payload, result)
        self.assertFalse(TbPersonagem.objects.exists())
        self.assertFalse(TbPersonagemCacador.objects.exists())
        self.payload['hunter_secrets'] = ['invalid']
        self.assertTrue(self.resolve(self.payload)[1])

    def test_legacy_creation_does_not_bind_from_client_fields(self):
        self.setup_creation()
        payload = self._payload('cacador')
        payload['estilo_luta'] = self.payload['estilo_luta']
        payload.update(hunter_ability='int', ruleset=self.ruleset.pk)
        result, errors = views._criador_resolver(payload)
        self.assertEqual(errors, [])
        with transaction.atomic():
            person = views._criador_persistir(self.user, payload, result)
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe__id_personagem=person).exists())

    def test_explicit_revision_preview_and_create_share_binding_without_preview_writes(self):
        self.setup_creation()
        _, errors = self.valid_payload('int')
        self.assertEqual(errors, [])
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''), \
                patch('home.views._criador_resolver', side_effect=self.resolve):
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            self.assertTrue(preview['ready'], preview)
            self.assertEqual(preview['erros'], [])
            self.assertFalse(TbPersonagem.objects.exists())
            self.assertFalse(TbPersonagemCacador.objects.exists())
            response = self._post_criar(self.user, self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.pv_maximo, preview['preview']['pv'])
        self.assertEqual(person.ca, preview['preview']['ca'])
        self.assertEqual(TbPersonagemCacador.objects.get(
            personagem_classe__id_personagem=person).ability, 'int')

    def test_preview_explains_missing_hunter_choice_without_writes(self):
        self.setup_creation()
        self.payload.pop('hunter_ability')
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''), \
                patch('home.views._criador_resolver', side_effect=self.resolve):
            response = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            creation = self._post_criar(self.user, self.payload)
        self.assertFalse(response['ready'])
        self.assertIn('Caçador', ' '.join(response['erros']))
        self.assertEqual(creation.status_code, 400)
        self.assertFalse(TbPersonagem.objects.exists())
        self.assertFalse(TbPersonagemCacador.objects.exists())
