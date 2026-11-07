"""Regressão Q03: Escola de Foco não é subclasse."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from home.character_engine import derive
from home.models import (
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbOpcaojogo,
    TbPersonagem,
    TbPersonagemClasse,
    TbPersonagemEscolha,
    TbSubclasse,
)
from home.picks import resolve_personagem
from home.views import _opcoes_ficha


class Q03IdentityTests(TestCase):
    """Cobre a identidade separada de subclasse e Escola de Foco."""

    def setUp(self):
        self.user = User.objects.create_user(username='q03-identidade', password='x')
        self.classe = TbClasse.objects.create(nome='Mago Q03', slug='mago-q03')
        self.guerra = TbSubclasse.objects.create(
            id_classe=self.classe, nome='Guerra Q03', slug='guerra-q03')
        TbSubclasse.objects.create(
            id_classe=self.classe, nome='Abjurador Q03', slug='abjurador-q03')
        TbClassehabilidade.objects.create(
            id_classe=self.classe,
            nome='Escolas de Foco Q03',
            descricao='Escolha uma escola de foco.',
            niveladquirido=1,
            tags_json=['pick:opcao:escola_de_foco:1'],
        )
        TbClassehabilidade.objects.create(
            id_classe=self.classe,
            id_subclasse=self.guerra,
            nome='Erudito da Guerra Q03',
            descricao='Marco mínimo para desbloquear a subclasse no nível 3.',
            niveladquirido=3,
        )
        self.abjuracao = TbOpcaojogo.objects.create(
            nome='Abjuração Q03', slug='abjuracao-q03', tipo='Escola de Foco')
        TbAcessoopcao.objects.create(
            id_opcao=self.abjuracao, id_classe=self.classe, nivel_recebimento=1)
        self.personagem = TbPersonagem.objects.create(
            dono=self.user, nome='Identidade Q03', nivel=3)
        self.personagem_classe = TbPersonagemClasse.objects.create(
            id_personagem=self.personagem,
            id_classe=self.classe,
            id_subclasse=self.guerra,
            nivel=3,
            principal=True,
        )

    def test_painel_persiste_abjuracao_sem_trocar_subclasse_guerra(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('personagem_escolher_opcoes', args=[self.personagem.pk]),
            {
                'classe': self.classe.pk,
                'slug': 'escola_de_foco',
                'opcao': self.abjuracao.slug,
            },
        )

        self.assertEqual(response.status_code, 302)
        escolha = TbPersonagemEscolha.objects.get(
            id_personagem=self.personagem, tipo='escola_de_foco', slot=0)
        self.assertEqual(escolha.id_opcao_id, self.abjuracao.pk)
        self.assertEqual(escolha.valor, self.abjuracao.slug)

        self.personagem_classe.refresh_from_db()
        self.assertEqual(self.personagem_classe.id_subclasse_id, self.guerra.pk)
        self.assertEqual(derive(self.personagem)['classes'], [{
            'classe': self.classe.nome,
            'subclasse': self.guerra.nome,
            'nivel': 3,
            'principal': True,
        }])

        banner = self.client.get(reverse('ficha_detail', args=[self.personagem.pk]))
        self.assertContains(
            banner,
            '<span class="banner-class">%s <em>(%s)</em> 3</span>' % (
                self.classe.nome, self.guerra.nome),
            html=True,
        )

    def test_escolha_legada_textual_sem_fk_permanece_foco_separado(self):
        TbPersonagemEscolha.objects.create(
            id_personagem=self.personagem,
            origem='%s: Escola de Foco' % self.classe.nome,
            tipo='escola_de_foco',
            slot=0,
            valor=self.abjuracao.slug,
        )

        grupo = next(
            group for group in resolve_personagem(self.personagem)
            if group['persist_tipo'] == 'escola_de_foco')
        self.assertEqual(len(grupo['escolhidas']), 1)
        self.assertIsNone(grupo['escolhidas'][0]['id_opcao'])
        self.assertEqual(grupo['escolhidas'][0]['valor'], self.abjuracao.slug)
        self.assertEqual(grupo['escolhidas'][0]['nome'], self.abjuracao.nome)

        painel = next(
            group for group in _opcoes_ficha(self.personagem)
            if group['tipo'] == 'escola_de_foco')
        self.assertEqual(painel['label'], 'Escola de Foco')
        self.assertEqual(painel['escolhidas'][0]['nome'], self.abjuracao.nome)
        self.personagem_classe.refresh_from_db()
        self.assertEqual(self.personagem_classe.id_subclasse_id, self.guerra.pk)
        self.assertEqual(derive(self.personagem)['classes'][0]['subclasse'], self.guerra.nome)
