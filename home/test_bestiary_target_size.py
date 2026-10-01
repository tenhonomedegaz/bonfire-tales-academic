from django.test import TestCase
from django.urls import reverse

from .bestiary_target_size import size_gate_note
from .models import TbBestiario


class BestiaryTargetSizeTests(TestCase):
    def setUp(self):
        self.wolf = TbBestiario.objects.create(
            slug='lobo-de-teste', nome='Lobo de Teste', tipo='Besta', tamanho='M',
            statblock_json={'actions': [{
                'name': 'Mordida',
                'entries': ['Ao acertar, o alvo Médio ou menor fica Caído.'],
                'tags_json': [
                    'instant{attack:melee, dmg:1d6+2(perfurante), '
                    'instant{trigger=hit, requires:target{size<=medio}, apply:caido}}'
                ],
            }]},
        )
        self.dire_wolf = TbBestiario.objects.create(
            slug='lobo-atroz-de-teste', nome='Lobo Atroz de Teste', tipo='Besta', tamanho='L',
            statblock_json={'actions': [{
                'name': 'Mordida',
                'entries': ['Ao acertar, o alvo Grande ou menor fica Caído.'],
                'tags_json': [
                    'instant{attack:melee, dmg:1d10+3(perfurante), '
                    'instant{trigger=hit, requires:target{size<=grande}, apply:caido}}'
                ],
            }]},
        )

    def test_catalog_resolves_selected_target_without_changing_creatures(self):
        url = reverse('mundo_bestiario')
        response = self.client.get(url, {'q': 'lobo', 'target_size': 'grande'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="target_size"')
        notes = {c['slug']: c['sb']['actions'][0]['size_gate_note']
                 for c in response.context['criaturas']}
        self.assertIn('não atendido', notes[self.wolf.slug])
        self.assertIn('atendido;', notes[self.dire_wolf.slug])
        self.assertNotIn('requires:target', response.content.decode())
        self.assertEqual(self.client.get(url, {'q': 'lobo'}).context['criaturas'][0]
                         ['sb']['actions'][0].get('size_gate_note'), None)
        self.wolf.refresh_from_db()
        self.assertEqual(self.wolf.statblock_json['actions'][0]['entries'],
                         ['Ao acertar, o alvo Médio ou menor fica Caído.'])

    def test_preview_resolves_target_size_and_rejects_invalid_input(self):
        url = reverse('api_creature_preview')
        allowed = self.client.get(url, {'slug': self.wolf.slug, 'target_size': 'medio'})
        blocked = self.client.get(url, {'slug': self.wolf.slug, 'target_size': 'grande'})
        plain = self.client.get(url, {'slug': self.wolf.slug})
        self.assertEqual((allowed.status_code, blocked.status_code, plain.status_code),
                         (200, 200, 200))
        self.assertIn('Limite de tamanho atendido', allowed.json()['statblock_html'])
        self.assertIn('Limite de tamanho não atendido', blocked.json()['statblock_html'])
        self.assertNotIn('Limite de tamanho', plain.json()['statblock_html'])
        self.assertNotIn('requires:target', blocked.json()['statblock_html'])
        self.assertEqual(self.client.get(url, {'slug': self.wolf.slug,
                                               'target_size': 'gigante demais'}).status_code, 400)

    def test_malformed_or_untagged_action_has_no_invented_result(self):
        self.assertEqual(size_gate_note(['instant{'], 'medio'), '')
        self.assertEqual(size_gate_note([], 'medio'), '')
        self.assertEqual(size_gate_note(['instant{attack:melee}'], 'medio'), '')

    def test_catalog_keeps_selected_creature_when_target_size_changes(self):
        url = reverse('mundo_bestiario')
        response = self.client.get(url, {
            'q': 'lobo', 'target_size': 'grande', 'active': self.wolf.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_creature_id'], self.wolf.pk)
        self.assertContains(response, f'name="active" value="{self.wolf.pk}"')
        self.assertContains(response, f'id="monster-{self.wolf.pk}" class="monster-panel "')

        missing = self.client.get(url, {
            'q': self.dire_wolf.nome, 'target_size': 'grande', 'active': self.wolf.pk,
        })
        self.assertEqual(missing.context['active_creature_id'], self.dire_wolf.pk)
        self.assertEqual(self.client.get(url, {'active': 'bad'}).status_code, 200)
