"""Exercise one character across the public Hunter entry points."""
import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from .hunter_catalog import compose_order_revision
from .models import TbPersonagem, TbPersonagemCacador
from . import test_creator_hunter_binding as creator_tests
from .test_criador import _CriadorBase


class HunterIntegratedFlowTests(_CriadorBase):
    setup_creation = creator_tests.CreatorHunterBindingTests.setup_creation
    valid_payload = creator_tests.CreatorHunterBindingTests.valid_payload

    def test_creation_laboratory_levelup_companion_and_sheet_share_revision(self):
        self.setup_creation()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        self.ruleset = compose_order_revision(
            self.ruleset, class_id=self.classe.pk, order_ids=orders)
        self.client.force_login(self.user)
        for ability in ('int', 'wis'):
            with self.subTest(ability=ability):
                self.assertEqual(self.valid_payload(ability)[1], [])
                with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
                    preview = self.client.post(reverse('criar_personagem_preview'),
                        data=self.payload, content_type='application/json')
                    self.assertTrue(preview.json()['ready'], preview.json())
                    count = TbPersonagem.objects.count()
                    created = self._post_criar(self.user, self.payload)
                self.assertEqual(created.status_code, 200, created.content)
                self.assertEqual(TbPersonagem.objects.count(), count + 1)
                person = TbPersonagem.objects.get(pk=created.json()['id'])
                profile = TbPersonagemCacador.objects.get(
                    personagem_classe__id_personagem=person)
                self.assertEqual((profile.ruleset_id, profile.ability),
                                 (self.ruleset.pk, ability))
                # Adventures authorize advancement; levels themselves change only via HTTP.
                person.aventuras = 100
                person.save(update_fields=['aventuras'])
                for level in (2, 3):
                    actions = [{'tipo': 'subir_nivel', 'payload': {'classe': self.classe.pk}}]
                    if level == 3:
                        actions.append({'tipo': 'subclasse', 'payload': {
                            'classe': self.classe.pk,
                            'subclasse': orders['ordem-da-alianca-selvagem']}})
                    body = {'acoes': actions}
                    preview = self.client.post(reverse('personagem_levelup_preview',
                        args=[person.pk]), data=body, content_type='application/json')
                    self.assertTrue(preview.json()['ready'], preview.json())
                    self.assertEqual(preview.json()['erros'], [])
                    person.refresh_from_db()
                    self.assertEqual(person.nivel, level - 1)
                    applied = self.client.post(reverse('personagem_levelup_aplicar',
                        args=[person.pk]), data=body, content_type='application/json')
                    self.assertEqual(applied.status_code, 200, applied.content)
                    self.assertEqual(applied.json()['ficha'], preview.json()['preview'])
                with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum):
                    lab = self.client.get(reverse('hunter_laboratory'), {
                        'level': 3, 'ability': ability, 'order': 'ordem-da-alianca-selvagem'})
                self.assertEqual(lab.status_code, 200)
                self.assertEqual(lab.context['ruleset_checksum'], self.ruleset.checksum)
                self.assertContains(lab, 'Companheiro Primordial')
                self.assertEqual([entry['block']['hp_max'] for entry in lab.context['companion_examples']],
                                 [60, 50, 50])
                self.assertContains(lab, 'Espreitador')
                profile.refresh_from_db()
                preparation_url = reverse('hunter_preparation', args=[person.pk])
                summoned = self.client.post(preparation_url, {
                    'action': 'companion', 'companion_event': 'summon',
                    'operation_id': str(uuid.uuid4()), 'version': profile.version,
                    'confirmed': '1', 'form': 'Lobo integrado', 'battle_form': 'bruto',
                    'creature_type': 'Fera', 'evolution': ['audicao-faro']})
                self.assertEqual(summoned.status_code, 302)
                profile.refresh_from_db()
                self.assertTrue(profile.companion.get('active'), profile.companion)
                commanded = self.client.post(preparation_url, {
                    'action': 'companion', 'companion_event': 'command',
                    'operation_id': str(uuid.uuid4()), 'version': profile.version,
                    'confirmed': '1', 'companion_turn': f'{ability}/round-1',
                    'command_mode': 'bonus', 'rend_count': '1'})
                self.assertEqual(commanded.status_code, 302)
                profile.refresh_from_db()
                self.assertEqual(profile.companion['last_command']['rend_attacks'], 1)
                sheet = self.client.get(reverse('hunter_sheet', args=[person.pk]))
                self.assertContains(sheet, 'Lobo integrado')
                self.assertContains(sheet, 'PV 60/60')
                self.assertTrue(person.magias.filter(
                    id_magia__nome_ingles='Battle Familiar', sempre_preparada=True).exists())
                self.assertContains(sheet, f'{ability}/round-1')
                self.assertContains(sheet, 'Ordem da Aliança Selvagem')
                self.assertEqual(profile.ruleset_id, self.ruleset.pk)
                self.assertTrue(person.magias.filter(
                    id_magia__nome_ingles="Hunter's Mark", sempre_preparada=True).exists())
