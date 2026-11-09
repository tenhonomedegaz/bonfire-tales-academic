"""Public race pages expose existing manifestations independently of portrait art."""
from django.urls import reverse

from .test_criador import _CriadorBase


class RaceElementOptionsTests(_CriadorBase):
    def test_all_races_and_ajax_include_the_same_manifestation_catalog(self):
        for slug in ('anao', 'elfo', 'humano', 'orc'):
            for query in ({}, {'ajax': '1'}):
                with self.subTest(race=slug, ajax=bool(query)):
                    response = self.client.get(reverse('raca_detail', args=[slug]), query)
                    self.assertEqual(response.status_code, 200)
                    options = response.context['race_origin_options']['elemental']
                    self.assertEqual({o['slug'] for o in options}, {'ifrit', 'undine', 'oread', 'sylph'})
                    self.assertContains(response, 'id="raceOriginOptions"')
