"""Expertise must accept proficiency granted by racial tags, not only saved rows."""
from . import picks
from .character_engine import derive
from .models import TbClasse, TbLinhagem, TbPersonagem, TbPersonagemClasse, TbRaca
from .test_criador import _CriadorBase


class ExpertiseOriginTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario('expertise-origins')
        self.person = TbPersonagem.objects.create(
            dono=self.user, nome='Elfo Lunareth', nivel=3, sabedoria=16,
            id_raca=TbRaca.objects.get(slug='elfo'),
            id_linhagem=TbLinhagem.objects.get(slug='lunareth'))
        self.pc = TbPersonagemClasse.objects.create(
            id_personagem=self.person, id_classe=TbClasse.objects.get(slug='cacador'),
            principal=True, nivel=3)
        self.person.pericias.create(nome='Natureza', atributo='INT', proficiente=True)

    def test_tag_proficiency_is_eligible_without_creating_a_manual_row(self):
        skill = next(s for s in derive(self.person)['pericias'] if s['nome'] == 'Percepção')
        self.assertTrue(skill['proficiente'])
        self.assertFalse(self.person.pericias.filter(nome='Percepção').exists())
        options = picks._pericia_expertise_universe({'personagem': self.person})
        self.assertIn('percepcao', {o['slug'] for o in options})
        self.assertNotIn('atletismo', {o['slug'] for o in options})

    def test_racial_expertise_persists_and_applies_only_one_extra_proficiency(self):
        before = next(s for s in derive(self.person)['pericias'] if s['nome'] == 'Percepção')
        groups = [g for g in picks.resolve_personagem(self.person)
                  if g['kind'] == 'pericia_expertise']
        self.assertTrue(groups)
        group = groups[0]
        self.assertIn('percepcao', {o['slug'] for o in group['universo']})
        self.assertFalse(picks.registry_entry(group['kind'])['validate'](group, ['percepcao']))
        group['slot_base'] = 0
        picks.registry_entry(group['kind'])['persist'](self.person, group, ['percepcao'])
        self.person.refresh_from_db()
        after = next(s for s in derive(self.person)['pericias'] if s['nome'] == 'Percepção')
        self.assertTrue(after['expertise'])
        self.assertEqual(after['bonus'], before['bonus'] + 2)
        options = picks._pericia_expertise_universe({'personagem': self.person})
        self.assertNotIn('percepcao', {o['slug'] for o in options})
