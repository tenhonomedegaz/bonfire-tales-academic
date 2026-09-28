import json

from django.test import override_settings
from django.urls import reverse

from .models import TbAntecedente, TbClasse, TbPersonagem, TbPersonagemCacador, TbRaca
from .test_creator_hunter_binding import CreatorHunterBindingTests
from .test_criador import _CriadorBase


class HunterPublicCreatorTests(_CriadorBase):
    setup_creation = CreatorHunterBindingTests.setup_creation
    valid_payload = CreatorHunterBindingTests.valid_payload
    def test_configured_revision_serves_catalog_preview_and_create_without_resolver_patch(self):
        self.setup_creation()
        self.assertEqual(self.valid_payload('int')[1], [])
        self.payload['ruleset'] = 'cliente-nao-escolhe-revisao'
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            TbClasse.objects.filter(pk=self.classe.pk).update(nome='Classe viva alterada', tags_json=[])
            TbRaca.objects.filter(slug='anao').update(nome='Raça viva alterada')
            TbAntecedente.objects.filter(slug='acolito').update(nome='Antecedente vivo alterado')
            default_page = self.client.get(reverse('criacao_ficha'))
            self.assertEqual(default_page.status_code, 200)
            self.assertNotIn('cacador', [c['slug'] for c in default_page.context['catalogos']['classes']])
            self.assertContains(default_page, 'Criar Caçador')
            page = self.client.get(reverse('criacao_ficha') + '?hunter=1')
            self.assertEqual(page.status_code, 200)
            self.assertEqual([c['slug'] for c in page.context['catalogos']['classes']], ['cacador'])
            hunter = next(c for c in page.context['catalogos']['classes'] if c['slug'] == 'cacador')
            self.assertTrue(hunter['hunter_rework'])
            self.assertEqual(hunter['nome'], self.classe.nome)
            race = next(r for r in page.context['catalogos']['racas'] if r['slug'] == 'anao')
            background = next(a for a in page.context['catalogos']['antecedentes'] if a['slug'] == 'acolito')
            self.assertNotEqual(race['nome'], 'Raça viva alterada')
            self.assertNotEqual(background['nome'], 'Antecedente vivo alterado')
            self.assertEqual(next(r for r in default_page.context['catalogos']['racas'] if r['slug'] == 'anao')['nome'], 'Raça viva alterada')
            self.assertContains(page, 'cf-hunter-ability')
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            self.assertTrue(preview['ready'], preview)
            self.assertEqual(preview['erros'], [])
            self.assertFalse(TbPersonagem.objects.exists())
            response = self._post_criar(self.user, self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.pv_maximo, preview['preview']['pv'])
        self.assertEqual(TbPersonagemCacador.objects.get(
            personagem_classe__id_personagem=person).ruleset_id, self.ruleset.pk)

    def test_client_cannot_select_revision_when_server_has_not_published_it(self):
        self.setup_creation()
        self.client.force_login(self.user)
        self.payload['ruleset'] = self.ruleset.pk
        page = self.client.get(reverse('criacao_ficha'))
        self.assertEqual(page.status_code, 200)
        hunter = next(c for c in page.context['catalogos']['classes'] if c['slug'] == 'cacador')
        self.assertFalse(hunter['hunter_rework'])
        response = self._post_criar(self.user, self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_missing_ability_and_invalid_published_checksum_fail_without_writes(self):
        self.setup_creation()
        self.assertEqual(self.valid_payload('wis')[1], [])
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
            self.payload['hunter_ability'] = ''
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            self.assertFalse(preview['ready'])
            self.assertIn('Ca', ' '.join(preview['erros']))
            response = self._post_criar(self.user, self.payload)
            self.assertEqual(response.status_code, 400)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='0' * 64):
            self.assertEqual(self.client.get(reverse('criacao_ficha')).status_code, 503)
            self.assertEqual(self._post_criar(self.user, self.payload).status_code, 503)
        self.assertFalse(TbPersonagem.objects.exists())
        self.assertFalse(TbPersonagemCacador.objects.exists())
