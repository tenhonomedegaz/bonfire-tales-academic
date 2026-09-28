from pathlib import Path
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .hunter_rework import catalog, prepare, secret_cost
from .ranger_reference import extract_reference


class HunterPreparationTests(SimpleTestCase):
    def test_catalog_matches_complete_secret_source(self):
        data = catalog()
        root = Path(__file__).resolve().parent.parent
        source = extract_reference(root / 'ref/Classes Reworkadas' / data['source_file'])
        self.assertEqual(data['source_sha256'], source['source_sha256'])
        self.assertEqual(data['progression'], source['progression'])
        secrets = {e['id']: e for e in source['entries']
                   if e['owner'].startswith('Linha:') and e['heading'] == 'h5'}
        self.assertEqual(len(data['secrets']), 30)
        self.assertEqual({s['source_id'] for s in data['secrets']}, set(secrets))
        for secret in data['secrets']:
            self.assertEqual(secret['text'], secrets[secret['source_id']]['text'])
        self.assertEqual(len(data['exclusive_secrets']), 8)
        self.assertEqual({row['order'] for row in data['exclusive_secrets']},
                         {row['id'] for row in data['orders']})
        source_by_id = {entry['id']: entry for entry in source['entries']}
        for exclusive in data['exclusive_secrets']:
            self.assertEqual(exclusive['level'], 18)
            self.assertEqual(exclusive['cost'], 4)
            self.assertEqual(exclusive['text'], source_by_id[exclusive['source_id']]['text'])
        full = json.loads((root / 'home/rules/hunter_content.json').read_text(encoding='utf-8'))
        self.assertEqual(full['source_sha256'], source['source_sha256'])
        self.assertEqual(full['progression'], source['progression'])
        self.assertEqual(len(full['features']), 84)
        self.assertEqual(len([row for row in full['features'] if row['order']]), 59)
        for feature in full['features']:
            original = source_by_id[feature['id']]
            self.assertEqual((feature['name'], feature['level'], feature['text']),
                             (original['name'], original['level'], original['section_text']))
        self.assertEqual([o['name'] for o in data['orders']], source['orders'])

    def test_all_orders_and_levels_unlock_exact_degrees(self):
        for order in catalog()['orders']:
            for level in range(3, 21):
                result = prepare(level=level, ability='int', order=order['id'])
                degree = 1 + (level >= 5) + (level >= 9) + (level >= 13)
                self.assertEqual(max(s['degree'] for s in result['options']), degree)
                self.assertTrue(result['available'])
                self.assertTrue(all(s['line'] == order['line'] for s in result['available']
                                    if s not in result['exclusive']))
                self.assertTrue(all(s['order'] == order['id'] for s in result['exclusive']))
                self.assertEqual(len(result['exclusive']), int(level >= 18))
                self.assertEqual(result['points'], level)

    def test_preparation_rejects_locked_unknown_duplicate_and_excess(self):
        for selected in (['unknown'], ['granada-de-luz'] * 2,
                         ['granada-de-luz', 'extrato-de-raiz-amarga', 'balsamo-elemental'],
                         ['catalisador-da-cacada']):
            with self.assertRaises(ValueError):
                prepare(level=2, ability='wis', selected=selected)
        result = prepare(level=2, total_level=5, ability='wis', selected=[
            'granada-de-luz', 'extrato-de-raiz-amarga', 'balsamo-elemental'])
        self.assertEqual(len(result['available']), 3)
        self.assertEqual(result['points'], 2)
        self.assertEqual(secret_cost(result, 'granada-de-luz', enhanced=True), 2)
        with self.assertRaises(ValueError):
            secret_cost(result, 'sinal-veritas')

    def test_master_line_cannot_consume_optional_preparation(self):
        order = next(o for o in catalog()['orders'] if 'Mutantes' in o['name'])
        with self.assertRaises(ValueError):
            prepare(level=3, ability='int', order=order['id'], selected=['granada-de-luz'])
        with self.assertRaises(ValueError):
            prepare(level=2, ability='int', order=order['id'])
        with self.assertRaises(ValueError):
            prepare(level=3, ability='int')

    def test_first_level_keeps_zero_dispel_circle_and_no_secrets(self):
        result = prepare(level=1, ability='wis')
        self.assertEqual(result['mark_dispel_level'], 0)
        self.assertEqual(result['points'], 0)
        self.assertEqual(result['options'], [])
        self.assertEqual(result['progression']['slots'], [2, 0, 0, 0, 0])


class HunterLaboratoryTests(TestCase):
    def test_published_revision_overrides_local_files_and_live_class_content(self):
        from unittest.mock import patch
        from django.test import override_settings
        from .models import TbClasse, TbClassehabilidade, TbPersonagem
        from .content_versions import create_revision, seal_ruleset
        from .versioned_classes import inventory_class, EVALUATOR, VOCABULARY

        hunter = TbClasse.objects.create(nome='Caçador', slug='cacador')
        feature = TbClassehabilidade.objects.create(id_classe=hunter,
            nome='Habilidade publicada', descricao='Descrição selada', niveladquirido=1)
        data = catalog()
        data['secrets'][0]['name'] = 'Segredo da revisão publicada'
        ruleset = seal_ruleset([
            create_revision('hunter-rework', data),
            create_revision('class-catalog:%s' % hunter.pk, inventory_class(hunter.pk)),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        feature.nome = 'Nome alterado depois da publicação'
        feature.save()
        self.client.force_login(get_user_model().objects.create_user(username='published-lab'))
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=ruleset.checksum), \
                patch('home.hunter_views.catalog', side_effect=AssertionError('local catalog read')), \
                patch('home.hunter_rework.level_features', side_effect=AssertionError('local descriptions read')):
            response = self.client.get(reverse('hunter_laboratory'), {'level': 2})
            missing_order = self.client.get(reverse('hunter_laboratory'), {
                'level': 3, 'order': data['orders'][0]['id']})
        self.assertContains(response, 'Habilidade publicada')
        self.assertContains(response, 'Descrição selada')
        self.assertContains(response, 'Segredo da revisão publicada')
        self.assertContains(response, ruleset.checksum)
        self.assertNotContains(response, feature.nome)
        self.assertContains(missing_order, 'não tem identidade única', status_code=400)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_missing_published_revision_does_not_fall_back_to_draft(self):
        from django.test import override_settings
        self.client.force_login(get_user_model().objects.create_user(username='missing-lab'))
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='missing'):
            response = self.client.get(reverse('hunter_laboratory'))
        self.assertContains(response, 'revisão publicada do Caçador está indisponível', status_code=503)

    def test_authenticated_preparation_and_invalid_input_do_not_create_characters(self):
        from .models import TbPersonagem
        url = reverse('hunter_laboratory')
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user(username='hunter-lab')
        self.client.force_login(user)
        count = TbPersonagem.objects.count()
        response = self.client.get(url, {'level': 2, 'ability': 'int', 'secret': ['granada-de-luz']})
        self.assertContains(response, 'Granada de Luz')
        self.assertEqual(response.context['result']['selected'], ['granada-de-luz'])
        self.assertContains(response, 'Estilo de Luta')
        for order in catalog()['orders']:
            response = self.client.get(url, {'level': 20, 'ability': 'int', 'order': order['id']})
            self.assertEqual(response.status_code, 200)
            features = response.context['features']
            self.assertTrue(any(f['order'] == order['name'] and f['level'] == 18 for f in features))
            for feature in features:
                self.assertContains(response, feature['name'])
        self.assertEqual(self.client.get(url, {'level': 2, 'secret': ['invalid']}).status_code, 400)
        self.assertEqual(TbPersonagem.objects.count(), count)

    def test_combat_conditions_render_without_creating_characters(self):
        from .models import TbPersonagem
        self.client.force_login(get_user_model().objects.create_user(username='hunter-combat'))
        url = reverse('hunter_laboratory')
        count = TbPersonagem.objects.count()
        params = {'level': 20, 'ability': 'wis', 'wisdom': 18,
                  'order': catalog()['orders'][0]['id'], 'marked': '1', 'favored': '1'}
        response = self.client.get(url, params)
        self.assertContains(response, '1d12')
        self.assertEqual(response.context['combat']['spell_dc'], 18)
        self.assertEqual(response.context['combat']['attacks'], 3)
        response = self.client.get(url, dict(params, third_used='1'))
        self.assertEqual(response.context['combat']['attacks'], 2)
        response = self.client.get(url, dict(params, order='ordem-dos-exterminadores',
            final_hunt='1', injured='1', protective_ability='wis', enemy_hit_this_turn='1'))
        self.assertContains(response, '2d12')
        self.assertEqual(response.context['combat']['damage_reduction'], 4)
        self.assertEqual(response.context['combat']['executor_ac_bonus'], 4)
        self.assertEqual(self.client.get(url, dict(params, wisdom='invalid')).status_code, 400)
        self.assertEqual(TbPersonagem.objects.count(), count)
