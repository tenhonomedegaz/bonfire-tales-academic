"""Sense and spell cards remain distinct through declarative references."""
from django.urls import reverse

from .models import TbTracoracial
from .test_criador import _CriadorBase


class RacialSenseReferenceTests(_CriadorBase):
    def test_racial_trait_points_to_sense_without_rewriting_the_spell_card(self):
        trait = TbTracoracial.objects.get(nome='Olhos da Verdade Primordial')
        self.assertIn('[Visão Verdadeira](tbRegra, truesight)', trait.descricao)
        self.assertNotIn('(tbMagia, visao-verdadeira)', trait.descricao)
        sense = self.client.get(reverse('api_card_preview'), {'table': 'tbRegra', 'args': 'truesight'})
        spell = self.client.get(reverse('api_card_preview'), {'table': 'tbMagia', 'args': 'visao-verdadeira'})
        self.assertEqual(sense.status_code, 200)
        self.assertEqual(spell.status_code, 200)
        self.assertEqual(sense.json()['kind'], 'rule')
        self.assertEqual(spell.json()['kind'], 'spell')
        self.assertIn('regra-truesight', sense.json()['url'])
        self.assertNotEqual(sense.json()['url'], spell.json()['url'])
        self.assertEqual(trait.nivel_requisito, 17)
