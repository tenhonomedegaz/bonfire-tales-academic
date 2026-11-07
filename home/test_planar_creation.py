"""Q15: planar choices must be resolved at creation, before any level-up."""
from home import picks, views
from home.models import TbTracoracial
from home.test_criador import _CriadorBase


class PlanarCreationTests(_CriadorBase):
    def payload(self):
        return self._payload('guerreiro', essencia_slug='nephilim')

    def menus(self):
        return [{'tipo': kind, 'fonte': 'Sangue Planar', 'valores': [value]}
                for kind, value in [('polo', 'celestial'), ('energia', 'lumen'),
                                    ('elemento', 'fogo')]]

    def test_missing_and_invalid_choices_are_rejected_before_creation(self):
        data = self.payload()
        _, missing = views._criador_resolver(data)
        data.setdefault('escolhas_raca', {})['menus'] = self.menus()
        _, valid = views._criador_resolver(data)
        self.assertEqual(valid, [])
        self.assertEqual(len(missing), 3, missing)
        for values in ([], ['invalid'], ['fogo', 'frio'], ['fogo', 'fogo']):
            data['escolhas_raca']['menus'][2]['valores'] = values
            _, errors = views._criador_resolver(data)
            self.assertTrue(errors, values)

    def test_three_choices_persist_at_level_one_and_have_no_remaining_group(self):
        data = self.payload()
        data.setdefault('escolhas_raca', {})['menus'] = self.menus()
        resolved, errors = views._criador_resolver(data)
        self.assertEqual(errors, [])
        character = views._criador_persistir(self._novo_usuario('q15'), data, resolved)
        self.assertEqual(character.nivel, 1)
        groups = [g for g in picks.resolve_personagem(character) if g['origem'] == 'Sangue Planar']
        self.assertEqual({g['kind'] for g in groups}, {'polo', 'energia', 'elemento'})
        self.assertTrue(all(g['pendentes'] == 0 for g in groups), groups)
        self.assertEqual(character.escolhas.filter(origem='Sangue Planar').count(), 3)
        from home.character_engine import derive
        resistances = str(derive(character)['resistencias']).lower()
        self.assertIn('fogo', resistances)
        self.assertIn('radiante', resistances)

    def test_stale_menus_do_not_grant_choices_without_essence(self):
        data = self._payload('guerreiro')
        data.setdefault('escolhas_raca', {})['menus'] = self.menus()
        resolved, errors = views._criador_resolver(data)
        self.assertEqual(errors, [])
        character = views._criador_persistir(self._novo_usuario('q15-stale'), data, resolved)
        self.assertFalse(character.escolhas.filter(origem='Sangue Planar').exists())

    def test_content_groups_use_the_shared_registry(self):
        trait = TbTracoracial.objects.get(nome='Sangue Planar')
        groups = views._racial_menu_groups([trait])
        self.assertEqual({g['kind']: g['n'] for g in groups},
                         {'polo': 1, 'energia': 1, 'elemento': 1})
        catalogs = views._criador_catalogos()
        menus = [g for g in catalogs['racial_choices_essencia']['nephilim'] if g.get('menu')]
        self.assertEqual({g['tipo'] for g in menus}, {'polo', 'energia', 'elemento'})
        self.assertTrue(all(g['opcoes'] for g in menus))
