"""Racial qualifiers use saved choices and passive tags without talent-name rules."""
from types import SimpleNamespace

from .models import TbEssencia, TbPersonagem, TbRaca, TbTracoracial
from .racial_prerequisites import prerequisite_filter
from .test_criador import _CriadorBase
from .views import _lvl_aplicar_talento_racial, _pendencias_talento_racial


class DraconicRacialPrerequisitesTests(_CriadorBase):
    def setUp(self):
        self.person = TbPersonagem.objects.create(dono=self._novo_usuario('draconic-qa'),
            nome='Draconic boundary', nivel=5, id_raca=TbRaca.objects.get(slug='humano'),
            id_essencia=TbEssencia.objects.get(slug='draconica'))
        self.person.escolhas.create(origem='Essencia', tipo='alento', slot=0, valor='fogo')
        self.person.talentos.create(categoria='racial', nivel=1, nome='Alento de Fogo: Reflexão Incandescente')

    def test_level_five_options_confirm_and_passive_descendancy_blocks_other_branches(self):
        options = {o['nome'] for group in _pendencias_talento_racial(self.person)
                   if group['nivel'] == 5 for o in group['opcoes']}
        self.assertIn('Transformação: Despertar do Long', options)
        self.assertIn('Transformação: Despertar do Draco', options)
        self.assertIn('Transformação: Despertar do Wyvern', options)
        self.assertEqual(_lvl_aplicar_talento_racial(self.person,
            {'nivel': 5, 'talento': 'Transformação: Despertar do Long'}), [])
        self.person.refresh_from_db()
        accepts = prerequisite_filter(self.person)
        def trait(name):
            return TbTracoracial.objects.get(nome=name)
        self.assertTrue(accepts(trait('Transformação: Despertar do Long'), 5))
        self.assertFalse(accepts(trait('Transformação: Despertar do Draco'), 5))
        self.assertFalse(accepts(trait('Transformação: Despertar do Wyvern'), 5))
        self.assertTrue(accepts(trait('Alento de Fogo: Reflexão Incandescente'), 5))
        self.assertFalse(accepts(trait('Alento de Água: Fôlego da Maré'), 5))

    def test_qualifier_value_in_an_unrelated_choice_cannot_satisfy_it(self):
        self.person.escolhas.filter(tipo='alento').delete()
        self.person.escolhas.create(origem='Unrelated', tipo='idioma', slot=0, valor='fogo')
        source = SimpleNamespace(id_raca_id=None, pre_requisito='Alento de Fogo.')
        self.assertFalse(prerequisite_filter(self.person)(source, 5))
