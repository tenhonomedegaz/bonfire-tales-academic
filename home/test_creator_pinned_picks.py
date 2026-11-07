from django.contrib.auth import get_user_model
from django.test import TestCase

from home.content_versions import seal_ruleset
from home.models import (TbAcessoopcao, TbClasse, TbItemMundano, TbOpcaojogo,
                         TbPersonagem, TbPersonagemEscolha, TbPersonagemProficiencia,
                         TbPersonagemTalento, TbRulesetContent, TbTalento,
                         TbClassehabilidade)
from home.picks import PICK_REGISTRY, resolve_builder
from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
from home.versioned_items import snapshot_mundane_items
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.content_versions import create_revision


class CreatorPinnedPicksTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(
            nome='Pinned creator', slug='pinned-creator',
            tags_json=['prof{armas_simples}'])
        self.feature = TbClassehabilidade.objects.create(
            id_classe=self.classe, nome='Pinned choices', descricao='', niveladquirido=1,
            tags_json=['pick:opcao:estilo:1', 'pick:arma:1',
                       'pick:ferramenta:ferramenta_artesao:1', 'pick:talento:1(tipo:geral)'])
        self.option = TbOpcaojogo.objects.create(
            nome='Pinned style', slug='pinned-style', tipo='Estilo', tags_json=['ca:+1'])
        TbAcessoopcao.objects.create(id_opcao=self.option, id_classe=self.classe,
                                     nivel_recebimento=1)
        self.weapon = TbItemMundano.objects.create(
            nome='Pinned blade', slug='pinned-blade', categoria='arma',
            subcategoria='arma_simples', tags_json=['dmg:1d6(cortante)'])
        self.tool = TbItemMundano.objects.create(
            nome='Pinned tools', slug='pinned-tools', categoria='ferramenta',
            subcategoria='ferramenta_artesao')
        self.talent = TbTalento.objects.create(
            nome='Pinned gift', slug='pinned-gift', tipo='geral', descricao='Frozen talent')
        self.ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk)),
            snapshot_options(), snapshot_mundane_items(), snapshot_origins()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.personagem = TbPersonagem.objects.create(
            dono=get_user_model().objects.create_user('pinned-picks'), nome='Pinned picks')

    def groups(self):
        return {group['kind']: group for group in resolve_builder(self.classe, ruleset=self.ruleset)}

    def test_builder_and_persist_stay_frozen_after_live_catalog_mutation(self):
        before = self.groups()
        self.assertEqual(before['opcao']['universo'][0]['nome'], 'Pinned style')
        self.assertEqual(before['arma']['universo'][0]['nome'], 'Pinned blade')
        self.assertEqual(before['ferramenta']['universo'][0]['nome'], 'Pinned tools')
        self.assertEqual(before['talento']['universo'][0]['nome'], 'Pinned gift')

        self.option.nome, self.option.tags_json = 'Changed style', ['ca:+9']
        self.option.save()
        self.feature.nome, self.feature.tags_json = 'Changed choices', []
        self.feature.save()
        self.weapon.nome, self.weapon.tags_json = 'Changed blade', ['dmg:9d9(fogo)']
        self.weapon.save()
        self.tool.nome = 'Changed tools'
        self.tool.save()
        self.talent.nome, self.talent.tipo = 'Changed gift', 'origem'
        self.talent.save()

        frozen = self.groups()
        self.assertEqual(frozen, before)
        PICK_REGISTRY['opcao']['persist'](self.personagem, frozen['opcao'], [self.option.slug])
        PICK_REGISTRY['arma']['persist'](self.personagem, frozen['arma'], [self.weapon.slug])
        PICK_REGISTRY['ferramenta']['persist'](self.personagem, frozen['ferramenta'], [self.tool.slug])
        PICK_REGISTRY['talento']['persist'](self.personagem, frozen['talento'], [self.talent.slug])

        option_choice = TbPersonagemEscolha.objects.get(id_personagem=self.personagem, tipo='estilo')
        self.assertEqual((option_choice.valor, option_choice.id_opcao_id), ('pinned-style', self.option.pk))
        self.assertTrue(TbPersonagemEscolha.objects.filter(
            id_personagem=self.personagem, tipo='maestria', valor='pinned-blade').exists())
        self.assertTrue(TbPersonagemProficiencia.objects.filter(
            id_personagem=self.personagem, tipo='ferramenta', nome='Pinned tools').exists())
        talent = TbPersonagemTalento.objects.get(id_personagem=self.personagem, id_talento=self.talent)
        self.assertEqual((talent.nome, talent.categoria), ('Pinned gift', 'geral'))

    def test_missing_frozen_catalog_content_fails_closed(self):
        incomplete = seal_ruleset([
            create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk))],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            resolve_builder(self.classe, ruleset=incomplete)

    def test_frozen_required_weapon_choice_cannot_disappear_or_unlock_all(self):
        self.classe.tags_json = []
        self.classe.save()
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk)),
            snapshot_options(), snapshot_mundane_items(), snapshot_origins()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        group = next(g for g in resolve_builder(self.classe, ruleset=ruleset) if g['kind'] == 'arma')
        self.assertEqual(group['universo'], [])
        self.assertTrue(PICK_REGISTRY['arma']['validate'](group, []))
        self.assertTrue(PICK_REGISTRY['arma']['validate'](group, [self.weapon.slug]))
