from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from home.models import TbTalento
from home.talent_presentation import attribute_presentation
from home.views import _talent_payload, talentos_view


class TalentAttributePresentationTests(SimpleTestCase):
    def test_choice_amount_and_cap_come_from_tags_without_category_or_name(self):
        for amount, cap in [(2, 30), (3, 28)]:
            result = attribute_presentation([
                f'attr:talent_attr_score+{amount}', f'attr_max:talent_attr_score={cap}'])
            self.assertEqual(result['aumento_atributo'],
                             f'+{amount} em um atributo de sua escolha, até {cap}')
            self.assertEqual(len(result['atributos_opcoes']), 6)

    def test_explicit_attribute_and_restricted_choice(self):
        fixed = attribute_presentation(['always_active{attr:str+3, attr_max:str=24}'])
        self.assertEqual(fixed['aumento_atributo'], '+3 em Força, até 24')
        self.assertEqual(fixed['atributos_opcoes'], ['Forca'])
        choice = attribute_presentation(['attr:talent_attr_score+2'], ['Inteligencia'])
        self.assertEqual(choice['atributos_opcoes'], ['Inteligencia'])

    def test_conditional_effects_are_not_reported_as_unconditional_increases(self):
        result = attribute_presentation([
            'while_active{attr:str+2}', 'always_active{requires:sangrando, attr:con+2}'])
        self.assertEqual(result['aumento_atributo'], 'Nenhum')

    def test_legacy_flags_and_malformed_tags_keep_safe_fallback(self):
        result = attribute_presentation(['always_active{'], ['Forca', 'Destreza'])
        self.assertEqual(result['atributos_str'], 'Forca, Destreza')
        self.assertEqual(result['atributos_opcoes'], ['Forca', 'Destreza'])

    def test_orm_payload_derives_metadata_without_changing_mechanical_flags(self):
        talent = TbTalento(nome='Qualquer fonte', tipo='geral',
                           tags_json=['attr:talent_attr_score+2', 'attr_max:talent_attr_score=30'])
        payload = _talent_payload(talent)
        self.assertIn('+2', payload['aumento_atributo'])
        self.assertIn('30', payload['aumento_atributo'])
        self.assertEqual(len(payload['atributos_opcoes']), 6)
        self.assertFalse(talent.atrib_forca)
        self.assertEqual(talent.tipo, 'geral')

    def test_postgres_document_path_uses_same_generic_reader(self):
        request = RequestFactory().get('/jogador/talentos/')
        request.user = SimpleNamespace(is_staff=False)
        tags = ['attr:talent_attr_score+2', 'attr_max:talent_attr_score=30']
        with patch('home.views._site_docs', return_value=[{'Nome': 'Qualquer', 'TagsJSON': tags}]), patch(
            'home.views.render', side_effect=lambda req, template, context: context
        ):
            context = talentos_view.__wrapped__(request)
        self.assertEqual(context['json_talentos'][0]['aumento_atributo'],
                         '+2 em um atributo de sua escolha, até 30')
