import json

from django.urls import reverse

from home.character_history import imported_initial_configuration_pending, level_one_rebuild_status
from home.character_log_models import CharacterLogSource
from home.models import TbPersonagem, TbPersonagemAventura
from home.test_criador import _CriadorBase


class ImportedInitialConfigurationTests(_CriadorBase):
    def setUp(self):
        self.owner = self._novo_usuario('initial-import-owner')
        self.other = self._novo_usuario('initial-import-other')
        self.person = TbPersonagem.objects.create(
            dono=self.owner, nome='Imported history shell', nivel=1,
            aventuras=12, carteira_pc=43210, braseiros=17)
        self.source = CharacterLogSource.objects.create(
            spreadsheet_id='initial-import-source', bot_log_id='123',
            owner=self.owner, discord_user_id='123', character=self.person,
            character_name=self.person.nome)
        self.ledger = TbPersonagemAventura.objects.create(
            id_personagem=self.person, nome_aventura='Approved historical mission',
            qtd_aventuras=12, nivel_no_lancamento=1, origem='mesa',
            detalhes_json={'contract': 'historical-log-delivery:v1',
                           'history_authority': 'registered_staff_log',
                           'source_id': self.source.pk, 'entry_id': 1,
                           'previously_paid_economy': True})

    def test_owner_configures_import_directly_and_keeps_history_and_economy(self):
        self.assertTrue(imported_initial_configuration_pending(self.person))
        self.assertTrue(level_one_rebuild_status(self.person)[0])
        self.client.force_login(self.owner)
        creation = reverse('criacao_ficha') + '?recriar=%s' % self.person.pk
        response = self.client.get(reverse('personagem_subir_nivel', args=[self.person.pk]))
        self.assertRedirects(response, creation, fetch_redirect_response=False)
        self.assertFalse(self.person.revisoes_build.exists())
        response = self.client.get(creation)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recriar_personagem'].pk, self.person.pk)
        response = self.client.get(reverse('ficha_detail', args=[self.person.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configurar ficha importada')
        self.assertTrue(response.context['configuracao_inicial_pendente'])
        response = self.client.post(reverse('personagem_recriar_nivel_1', args=[self.person.pk]),
            data=json.dumps(self._payload('guerreiro')), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.person.refresh_from_db()
        self.assertEqual((self.person.nivel, self.person.aventuras,
                          self.person.carteira_pc, self.person.braseiros), (1, 12, 43210, 17))
        self.assertEqual(self.person.classes.get(principal=True).id_classe.slug, 'guerreiro')
        self.assertEqual(list(self.person.aventuras_ledger.values_list('pk', flat=True)),
                         [self.ledger.pk])
        self.assertEqual(self.person.revisoes_build.filter(tipo='nivel_1').count(), 1)
        self.assertFalse(imported_initial_configuration_pending(self.person))
        TbPersonagemAventura.objects.create(
            id_personagem=self.person, nome_aventura='New session after configuration',
            qtd_aventuras=1, nivel_no_lancamento=1, origem='mesa')
        self.person.aventuras += 1
        self.person.save(update_fields=['aventuras'])
        self.assertFalse(level_one_rebuild_status(self.person)[0])

    def test_unattested_progress_and_other_owner_never_unlock_initial_setup(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('criacao_ficha') + '?recriar=%s' % self.person.pk)
        self.assertIn(response.status_code, (403, 404))
        self.source.owner = self.other
        self.source.save()
        self.assertFalse(level_one_rebuild_status(self.person)[0])
        self.source.owner = self.owner
        self.source.save()
        self.ledger.detalhes_json = {}
        self.ledger.save()
        self.assertFalse(level_one_rebuild_status(self.person)[0])
        self.assertFalse(imported_initial_configuration_pending(self.person))
