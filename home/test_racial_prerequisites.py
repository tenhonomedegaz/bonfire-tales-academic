"""Racial milestones validate dependencies without spending class talent slots."""
from .character_engine import derive
from .models import TbClasse, TbLinhagem, TbPersonagem, TbPersonagemClasse, TbRaca
from .pathbuilder import _apply_racial_talents, _orcamento
from .test_criador import _CriadorBase
from .views import _lvl_aplicar_talento_racial, _pendencias_talento_racial


class RacialPrerequisiteTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario('racial-prerequisites')
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Lunar hunter', nivel=17,
            id_raca=TbRaca.objects.get(slug='elfo'),
            id_linhagem=TbLinhagem.objects.get(slug='lunareth'), sabedoria=16)
        TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=TbClasse.objects.get(slug='cacador'), nivel=17, principal=True)
        self.person.talentos.create(categoria='racial', nivel=1, nome='Manto Selênico')

    def names(self, level):
        return {o['nome'] for g in _pendencias_talento_racial(self.person)
                if g['nivel'] == level for o in g['opcoes']}

    def caster_payload(self):
        from .models import TbMagia
        payload = self._payload('mago', raca_slug='elfo', linhagem_slug='lunareth')
        payload['talento_raca'] = 'Manto Selênico'
        n = len(payload['truques'])
        payload['truques'] = [m.slug for m in TbMagia.objects.filter(nivel=0)
                             if 'Mago' in (m.classes or '') and 'attack:magic' not in (m.tags_json or [])][:n]
        return payload

    def test_initial_creator_checks_independent_spells_and_rejects_self_grants_atomically(self):
        from .models import TbTracoracial
        user = self._novo_usuario('racial-creator', staff=True)
        payload = self._payload('guerreiro', raca_slug='elfo', linhagem_slug='lunareth')
        payload['talento_raca'] = 'Condutor da Trama'
        before = TbPersonagem.objects.count()
        rejected = self._post_criar(user, payload)
        self.assertEqual(rejected.status_code, 400, rejected.content[:600])
        self.assertIn('Pré-requisito', str(rejected.json()))
        self.assertEqual(TbPersonagem.objects.count(), before)
        from django.urls import reverse
        preview = self.client.post(reverse('criar_personagem_preview'), payload,
                                   content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(preview.json()['ready'])
        self.assertIn('Pré-requisito', str(preview.json()['erros']))
        self.assertEqual(TbPersonagem.objects.count(), before)
        candidate = TbTracoracial.objects.create(id_raca=self.person.id_raca,
            nome='Fonte circular de teste', talento_racial=True, nivel_requisito=1,
            pre_requisito='Elfo, capacidade de conjurar Raio de Fogo.',
            tags_json=['cast{spell:raio-de-fogo, modifiers{without{slot}, at_will}}'])
        payload['talento_raca'] = candidate.nome
        rejected = self._post_criar(user, payload)
        self.assertEqual(rejected.status_code, 400, rejected.content[:600])
        self.assertIn('Pré-requisito', str(rejected.json()))
        self.assertEqual(TbPersonagem.objects.count(), before)
        payload = self.caster_payload()
        payload['talento_raca'] = 'Condutor da Trama'
        payload['truques'][0] = 'raio-de-fogo'
        accepted = self._post_criar(user, payload)
        self.assertEqual(accepted.status_code, 200, accepted.content[:600])
        created = TbPersonagem.objects.get(dono=user)
        self.assertTrue(created.talentos.filter(categoria='racial', nome='Condutor da Trama').exists())
        self.assertEqual(created.magias.filter(id_magia__slug='raio-de-fogo').count(), 1)

    def test_laboratory_uses_spells_from_same_build_but_not_invalid_spell_sources(self):
        from .pathbuilder import simulate_build
        base = self.caster_payload()
        build = {'modo': 'sandbox', 'classes': [{'slug': 'mago', 'nivel': 5}],
            'talentos_raciais': [{'nivel': 5, 'nome': 'Condutor da Trama'}],
            'magias': [{'slug': 'raio-de-fogo', 'classe': 'mago', 'preparada': True}]}
        before = TbPersonagem.objects.count()
        result = simulate_build(self.user, base, build)
        self.assertFalse(any('Talento racial invalido' in p for p in result['validacao']['problemas']))
        self.assertIn('Condutor da Trama', {f['nome'] for f in result['features']})
        build['magias'][0]['classe'] = 'guerreiro'
        rejected = simulate_build(self.user, base, build)
        self.assertTrue(any('Talento racial invalido' in p for p in rejected['validacao']['problemas']))
        self.assertNotIn('Condutor da Trama', {f['nome'] for f in rejected['features']})
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_prerequisite_identity_uses_the_frozen_origin_not_live_names(self):
        from .models import TbTracoracial
        from .racial_prerequisites import prerequisite_filter
        from .test_creator_pinned_catalog import CreatorPinnedCatalogTests
        from .versioned_origins import VersionedOrigins
        mage = TbClasse.objects.get(slug='mago')
        ruleset = CreatorPinnedCatalogTests.seal(self, mage)
        candidate = next(row for row in VersionedOrigins(ruleset).objects(TbTracoracial)
                         if row.nome == 'Manto Selênico')
        self.person.classes.update(id_classe=mage, nivel=1)
        self.person.talentos.all().delete()
        self.person.nivel = 1
        self.person.save(update_fields=['nivel'])
        TbRaca.objects.filter(pk=self.person.id_raca_id).update(nome='Changed race')
        TbLinhagem.objects.filter(pk=self.person.id_linhagem_id).update(nome='Changed lineage')
        self.person.refresh_from_db()
        self.assertTrue(prerequisite_filter(self.person, ruleset=ruleset)(candidate, 1))

    def test_missing_named_and_at_will_prerequisites_are_not_offered_or_accepted(self):
        self.assertNotIn('Abertura Entre Fios', self.names(9))
        self.assertNotIn('Precisão Élfica de Perícia', self.names(9))
        self.assertNotIn('Olhos da Verdade Primordial', self.names(17))
        for level, name in ((9, 'Abertura Entre Fios'), (17, 'Olhos da Verdade Primordial')):
            self.assertTrue(_lvl_aplicar_talento_racial(self.person, {'nivel': level, 'talento': name}))
        self.assertEqual(self.person.talentos.count(), 1)
        self.assertIn('Vigília Selênica', self.names(9))
        self.assertIn('Disciplina das Lâminas Ancestrais', self.names(5))

    def test_laboratory_rechecks_dependencies_in_order_and_preserves_class_budget(self):
        before = _orcamento(self.person, derive(self.person), {'talentos': [], 'atributos_bonus': {}})
        groups, issues = _apply_racial_talents(self.person, {'talentos_raciais': [
            {'nivel': 5, 'nome': 'Disciplina das Lâminas Ancestrais'},
            {'nivel': 9, 'nome': 'Abertura Entre Fios'},
            {'nivel': 17, 'nome': 'Acerto das Mil Linhas'}]})
        self.assertEqual(issues, [])
        self.assertIn('Acerto das Mil Linhas', {o['nome'] for g in groups
            if g['nivel'] == 17 for o in g['opcoes']})
        after = _orcamento(self.person, derive(self.person), {'talentos': [], 'atributos_bonus': {}})
        self.assertEqual(before, after)
        self.assertEqual(self.person.talentos.filter(categoria='racial').count(), 4)

    def test_knowing_a_spell_is_not_the_same_as_casting_it_at_will(self):
        from .models import TbMagia
        spell = TbMagia.objects.get(slug='detectar-magia')
        self.person.magias.create(id_magia=spell, nome=spell.nome, nivel=spell.nivel,
                                 origem='Caçador', preparada=True)
        self.assertNotIn('Olhos da Verdade Primordial', self.names(17))
        groups, issues = _apply_racial_talents(self.person, {'talentos_raciais': [
            {'nivel': 5, 'nome': 'Olhos da Mana'},
            {'nivel': 17, 'nome': 'Olhos da Verdade Primordial'}]})
        self.assertEqual(issues, [])
        self.assertTrue(self.person.talentos.filter(nome='Olhos da Verdade Primordial').exists())

    def test_attack_spell_requirement_uses_spell_tags_not_class_spellcasting_alone(self):
        from .models import TbMagia
        self.assertNotIn('Condutor da Trama', self.names(5))
        spell = TbMagia.objects.get(slug='raio-de-fogo')
        self.person.magias.create(id_magia=spell, nome=spell.nome, nivel=spell.nivel,
                                 origem='Treinamento', preparada=True)
        self.assertIn('Condutor da Trama', self.names(5))
