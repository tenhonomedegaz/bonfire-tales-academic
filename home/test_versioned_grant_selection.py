from django.test import TestCase
from home.test_versioned_sync import VersionedSyncTests as Fixtures
from home.models import TbPersonagemEscolha, TbPersonagemMagia
from home.views import (_criador_magias_pendentes, _criador_aplicar_magias_concedidas,
                        _lvl_aplicar_magias_concedidas, CriadorEscolhasError)


class VersionedGrantSelectionTests(TestCase):
    def setUp(self):
        Fixtures.setUp(self)
        TbPersonagemEscolha.objects.filter(id_personagem=self.person, tipo='magia-concedida').delete()
        self.spell.nome = 'Changed name'
        self.spell.slug = 'changed-slug'
        self.spell.classes = ''
        self.spell.save()
        self.feature.tags_json = []
        self.feature.save()
        self.payload = {'fonte': 'Old feature', 'slot': 0, 'magias': ['pinned-spell']}

    def test_creator_displays_and_persists_frozen_selection(self):
        pending = _criador_magias_pendentes(self.person, ruleset=self.ruleset)
        self.assertEqual(pending[0]['opcoes'], [
            {'slug': 'pinned-spell', 'nome': 'Old spell', 'nome_ingles': 'Old English'}])
        for _ in range(2):
            _criador_aplicar_magias_concedidas(self.person,
                {'magias_concedidas': [self.payload]}, strict=True, ruleset=self.ruleset)
        self.assertEqual(TbPersonagemEscolha.objects.filter(id_personagem=self.person,
            tipo='magia-concedida').count(), 1)
        granted = TbPersonagemMagia.objects.get(id_personagem=self.person, sempre_preparada=True)
        self.assertEqual((granted.id_magia_id, granted.nome), (self.spell.pk, 'Old spell'))

    def test_creator_rejects_current_catalog_and_rolls_back_missing_identity(self):
        invalid = dict(self.payload, magias=['changed-slug'])
        with self.assertRaises(CriadorEscolhasError):
            _criador_aplicar_magias_concedidas(self.person,
                {'magias_concedidas': [invalid]}, strict=True, ruleset=self.ruleset)
        self.option.delete()
        with self.assertRaisesMessage(ValueError, 'Granted option identity unavailable'):
            _criador_aplicar_magias_concedidas(self.person,
                {'magias_concedidas': [self.payload]}, strict=True, ruleset=self.ruleset)
        self.assertFalse(TbPersonagemEscolha.objects.filter(id_personagem=self.person,
            tipo='magia-concedida').exists())
        self.assertFalse(TbPersonagemMagia.objects.filter(id_personagem=self.person,
            sempre_preparada=True).exists())

    def test_levelup_validates_frozen_pool_and_does_not_repeat_choice(self):
        self.assertTrue(_lvl_aplicar_magias_concedidas(self.person,
            dict(self.payload, magias=['changed-slug']), ruleset=self.ruleset))
        self.assertEqual(_lvl_aplicar_magias_concedidas(self.person,
            self.payload, ruleset=self.ruleset), [])
        self.assertTrue(_lvl_aplicar_magias_concedidas(self.person,
            self.payload, ruleset=self.ruleset))
        self.assertEqual(TbPersonagemEscolha.objects.filter(id_personagem=self.person,
            tipo='magia-concedida').count(), 1)
