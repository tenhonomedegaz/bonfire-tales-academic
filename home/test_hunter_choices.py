from django.test import TestCase
from .hunter_choices import favored_state
from .models import TbPersonagemEscolha


class HunterFavoredTests(TestCase):
    def setUp(self):
        from .test_hunter_preparation import HunterPersistentPreparationTests
        HunterPersistentPreparationTests.setUp(self)

    def save(self, selected, version):
        return self.client.post(self.url, {'action': 'favored', 'favored': selected, 'version': version})

    def test_progression_reload_and_idempotency(self):
        self.assertEqual(self.save(['bestas'], 0).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(favored_state(self.profile)['selected'], ['bestas'])
        self.assertContains(self.client.get(self.url), 'checked disabled')
        self.assertEqual(self.save(['bestas'], 1).status_code, 302)
        self.assertEqual(TbPersonagemEscolha.objects.filter(tipo='hunter-favored').count(), 1)
        self.pc.nivel = 8
        self.pc.save()
        self.assertEqual(self.save(['bestas', 'fadas'], 1).status_code, 302)
        self.pc.nivel = 14
        self.pc.save()
        self.assertEqual(self.save(['bestas', 'fadas', 'gigantes'], 2).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(favored_state(self.profile)['remaining'], 0)
        self.assertEqual(self.profile.version, 3)

    def test_invalid_replacement_stale_and_permission_preserve_choices(self):
        for values in (['unknown'], ['bestas', 'bestas'], [], ['bestas', 'fadas']):
            self.assertEqual(self.save(values, 0).status_code, 400)
        self.assertEqual(self.save(['bestas'], 0).status_code, 302)
        self.assertEqual(self.save(['fadas'], 1).status_code, 400)
        self.assertEqual(self.save(['bestas'], 0).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.save(['bestas'], 1).status_code, 404)
        self.assertEqual(list(TbPersonagemEscolha.objects.filter(tipo='hunter-favored')
                              .values_list('valor', flat=True)), ['bestas'])

    def test_level_reduction_preserves_history_and_frozen_catalog(self):
        from unittest.mock import patch
        self.save(['bestas'], 0)
        self.pc.nivel = 1
        self.pc.save()
        with patch('home.hunter_rework.catalog', side_effect=AssertionError('live catalog')):
            response = self.client.get(self.url)
        self.assertContains(response, 'precisam de regularização')
        self.assertEqual(self.save([], 1).status_code, 400)
        self.assertEqual(TbPersonagemEscolha.objects.filter(tipo='hunter-favored').count(), 1)

    def test_multiclass_does_not_unlock_hunter_choices(self):
        from .models import TbClasse, TbPersonagemClasse
        other = TbClasse.objects.create(nome='Other', slug='other-favored')
        TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=other, nivel=10)
        self.assertEqual(favored_state(self.profile)['limit'], 1)
        self.assertEqual(self.save(['bestas', 'fadas'], 0).status_code, 400)
