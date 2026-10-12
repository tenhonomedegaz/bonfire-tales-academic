# -*- coding: utf-8 -*-
"""SOCIAL DO PERFIL — curtir e seguir (pedido dos usuários).

Contrato provado aqui:
  1. CURTIR é toggle idempotente: 1º POST cria a linha e sobe a contagem, 2º POST
     apaga e desce; o JSON devolve o estado resultante e ele bate com o banco.
  2. SEGUIR idem, e é DIRECIONAL (A→B não implica B→A).
  3. A si mesmo é 400 nos dois endpoints, e NADA é gravado.
  4. Anônimo toma 302 (login_required) — e continua sem gravar nada.
  5. A prévia do editor (POST /perfil/previa/) não explode com o bloco social e
     NÃO emite botão (o dono não pode curtir/seguir a si mesmo).
  6. O perfil público mostra as contagens pra qualquer um (inclusive anônimo), e
     o cartão de /jogadores/ traz as contagens sem N+1 (batch em 2 queries).

Ambiente: nenhuma dependência de catálogo/cosmético — só auth.User + as duas
tabelas novas de memória.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from home.models import TbPerfilCurtida, TbPerfilSeguidor, UserProfile
from home import social as _social


class PerfilSocialBase(TestCase):
    """Dois jogadores: `ator` (quem interage) e `alvo` (dono do perfil visitado)."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ator = User.objects.create_user('ator', 'ator@example.com', 'senha-forte-1')
        self.alvo = User.objects.create_user('alvo', 'alvo@example.com', 'senha-forte-2')
        for u in (self.ator, self.alvo):
            perfil = UserProfile.objects.get_or_create(user=u)[0]
            # bio preenchida = "perfil customizado" → o usuário entra na listagem
            # de /jogadores/ mesmo sem personagem público.
            perfil.bio = 'Bio de %s' % u.username
            perfil.save()

    def url_curtir(self, username='alvo'):
        return reverse('perfil_curtir', args=[username])

    def url_seguir(self, username='alvo'):
        return reverse('perfil_seguir', args=[username])

    def login_ator(self):
        self.assertTrue(self.client.login(username='ator', password='senha-forte-1'))


class CurtirTests(PerfilSocialBase):

    def test_toggle_curtir_descurtir_persiste_e_conta(self):
        """POST curte (linha criada, contagem 1); POST de novo descurte (0)."""
        self.login_ator()

        r1 = self.client.post(self.url_curtir())
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1['ok'])
        self.assertTrue(d1['curtiu'])
        self.assertEqual(d1['curtidas'], 1)
        self.assertEqual(
            TbPerfilCurtida.objects.filter(quem=self.ator, alvo=self.alvo).count(), 1)

        r2 = self.client.post(self.url_curtir())
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertFalse(d2['curtiu'])
        self.assertEqual(d2['curtidas'], 0)
        self.assertEqual(
            TbPerfilCurtida.objects.filter(quem=self.ator, alvo=self.alvo).count(), 0)

    def test_curtida_nao_duplica_linha(self):
        """Curtir → descurtir → curtir deixa exatamente UMA linha (unique quem+alvo)."""
        self.login_ator()
        for _ in range(3):
            self.client.post(self.url_curtir())
        self.assertEqual(TbPerfilCurtida.objects.filter(alvo=self.alvo).count(), 1)

    def test_curtir_a_si_mesmo_400_e_nao_grava(self):
        self.login_ator()
        resp = self.client.post(self.url_curtir('ator'))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])
        self.assertEqual(TbPerfilCurtida.objects.count(), 0)

    def test_curtir_anonimo_302_e_nao_grava(self):
        resp = self.client.post(self.url_curtir())
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
        self.assertEqual(TbPerfilCurtida.objects.count(), 0)

    def test_curtir_get_nao_e_aceito(self):
        self.login_ator()
        self.assertEqual(self.client.get(self.url_curtir()).status_code, 405)
        self.assertEqual(TbPerfilCurtida.objects.count(), 0)


class SeguirTests(PerfilSocialBase):

    def test_toggle_seguir_deixar_de_seguir_persiste_e_conta(self):
        self.login_ator()

        r1 = self.client.post(self.url_seguir())
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1['segue'])
        self.assertEqual(d1['seguidores'], 1)
        self.assertEqual(
            TbPerfilSeguidor.objects.filter(seguidor=self.ator, alvo=self.alvo).count(), 1)

        r2 = self.client.post(self.url_seguir())
        d2 = r2.json()
        self.assertFalse(d2['segue'])
        self.assertEqual(d2['seguidores'], 0)
        self.assertEqual(TbPerfilSeguidor.objects.count(), 0)

    def test_seguir_e_direcional(self):
        """A seguir B não faz B seguir A: contagens de cada lado são independentes."""
        self.login_ator()
        self.client.post(self.url_seguir())

        self.assertEqual(_social.contagens(self.alvo)['seguidores'], 1)
        self.assertEqual(_social.contagens(self.alvo)['seguindo'], 0)
        self.assertEqual(_social.contagens(self.ator)['seguidores'], 0)
        self.assertEqual(_social.contagens(self.ator)['seguindo'], 1)

    def test_seguir_a_si_mesmo_400_e_nao_grava(self):
        self.login_ator()
        resp = self.client.post(self.url_seguir('ator'))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])
        self.assertEqual(TbPerfilSeguidor.objects.count(), 0)

    def test_seguir_anonimo_302_e_nao_grava(self):
        resp = self.client.post(self.url_seguir())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TbPerfilSeguidor.objects.count(), 0)


class PerfilPublicoSocialTests(PerfilSocialBase):

    def test_visitas_ao_perfil_sem_registro_nao_criam_dados(self):
        UserProfile.objects.filter(user=self.alvo).delete()
        url = reverse('public_profile', args=[self.alvo.username])
        with CaptureQueriesContext(connection) as queries:
            primeira = self.client.get(url)
            segunda = self.client.get(url)
        self.assertContains(primeira, self.alvo.username)
        self.assertContains(segunda, self.alvo.username)
        self.assertFalse(UserProfile.objects.filter(user=self.alvo).exists())
        self.assertEqual([
            q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
                ('INSERT ', 'UPDATE ', 'DELETE '))
        ], [])


    def test_contagens_aparecem_no_perfil_publico_para_anonimo(self):
        """Visitante anônimo vê as CONTAGENS, mas nenhum botão de ação."""
        TbPerfilCurtida.objects.create(quem=self.ator, alvo=self.alvo)
        TbPerfilSeguidor.objects.create(seguidor=self.ator, alvo=self.alvo)

        resp = self.client.get(reverse('public_profile', args=['alvo']))
        self.assertEqual(resp.status_code, 200)
        social = resp.context['social']
        self.assertEqual(social['curtidas'], 1)
        self.assertEqual(social['seguidores'], 1)
        self.assertFalse(social['pode_interagir'])
        self.assertFalse(social['autenticado'])

        html = resp.content.decode('utf-8')
        self.assertIn('profile-social', html)
        self.assertNotIn('data-social-action="curtir"', html)

    def test_visitante_logado_ve_botoes_com_estado_certo(self):
        TbPerfilCurtida.objects.create(quem=self.ator, alvo=self.alvo)
        self.login_ator()

        resp = self.client.get(reverse('public_profile', args=['alvo']))
        self.assertEqual(resp.status_code, 200)
        social = resp.context['social']
        self.assertTrue(social['pode_interagir'])
        self.assertTrue(social['curtiu'])
        self.assertFalse(social['segue'])

        html = resp.content.decode('utf-8')
        self.assertIn('data-social-action="curtir"', html)
        self.assertIn('data-social-action="seguir"', html)

    def test_dono_no_proprio_perfil_publico_nao_ve_botoes(self):
        self.login_ator()
        resp = self.client.get(reverse('public_profile', args=['ator']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['social']['is_self'])
        self.assertFalse(resp.context['social']['pode_interagir'])
        self.assertNotIn('data-social-action=', resp.content.decode('utf-8'))


class EditorEPreviewTests(PerfilSocialBase):

    def test_preview_do_editor_nao_explode_e_nao_emite_botao(self):
        """A prévia viva renderiza o MESMO partial com o bloco social — sem 500 e
        sem botão (o dono não pode curtir/seguir a si mesmo)."""
        TbPerfilSeguidor.objects.create(seguidor=self.alvo, alvo=self.ator)
        self.login_ator()

        resp = self.client.post(reverse('perfil_preview'), {
            'profile_theme': 'bonfire',
            'avatar_frame': '',
            'profile_effect': '',
            'bio': 'bio candidata',
        })
        self.assertEqual(resp.status_code, 200)
        dados = resp.json()
        self.assertTrue(dados['ok'])
        html = dados['html']
        self.assertIn('profile-social', html)
        self.assertIn('seguidor', html)
        self.assertNotIn('data-social-action=', html)

    def test_editor_lista_seguidores_e_seguindo(self):
        """/perfil/ (editor) traz contagens + listas simples de quem segue/curte."""
        TbPerfilSeguidor.objects.create(seguidor=self.alvo, alvo=self.ator)
        TbPerfilSeguidor.objects.create(seguidor=self.ator, alvo=self.alvo)
        TbPerfilCurtida.objects.create(quem=self.alvo, alvo=self.ator)
        self.login_ator()

        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['social']['seguidores'], 1)
        self.assertEqual(resp.context['social']['seguindo'], 1)
        self.assertEqual(resp.context['social']['curtidas'], 1)
        self.assertEqual([p['username'] for p in resp.context['social_seguidores']], ['alvo'])
        self.assertEqual([p['username'] for p in resp.context['social_seguindo']], ['alvo'])
        self.assertEqual([p['username'] for p in resp.context['social_curtidas']], ['alvo'])


class JogadoresBatchTests(PerfilSocialBase):

    def test_cards_trazem_contagens(self):
        TbPerfilCurtida.objects.create(quem=self.ator, alvo=self.alvo)
        TbPerfilSeguidor.objects.create(seguidor=self.ator, alvo=self.alvo)

        resp = self.client.get(reverse('jogadores'))
        self.assertEqual(resp.status_code, 200)
        por_user = {c['user'].username: c['social'] for c in resp.context['cards']}
        self.assertEqual(por_user['alvo'], {'curtidas': 1, 'seguidores': 1})
        self.assertEqual(por_user['ator'], {'curtidas': 0, 'seguidores': 0})

    def test_batch_sem_n_mais_1(self):
        """As contagens de N usuários custam SEMPRE 2 queries (uma por tabela)."""
        User = get_user_model()
        extras = [User.objects.create_user('extra%d' % i, 'e%d@x.com' % i, 'x' * 10)
                  for i in range(6)]
        for u in extras:
            TbPerfilCurtida.objects.create(quem=self.ator, alvo=u)
            TbPerfilSeguidor.objects.create(seguidor=self.ator, alvo=u)

        todos = [self.ator, self.alvo] + extras
        with self.assertNumQueries(2):
            out = _social.social_counts_batch(todos)
        self.assertEqual(len(out), len(todos))
        self.assertEqual(out[extras[0].pk], {'curtidas': 1, 'seguidores': 1})
        self.assertEqual(out[self.ator.pk], {'curtidas': 0, 'seguidores': 0})


class CascadeTests(PerfilSocialBase):

    def test_deletar_usuario_apaga_as_relacoes(self):
        """on_delete=CASCADE nas duas pontas: sumiu o user, sumiu a relação."""
        TbPerfilCurtida.objects.create(quem=self.ator, alvo=self.alvo)
        TbPerfilSeguidor.objects.create(seguidor=self.ator, alvo=self.alvo)
        TbPerfilSeguidor.objects.create(seguidor=self.alvo, alvo=self.ator)

        self.ator.delete()
        self.assertEqual(TbPerfilCurtida.objects.count(), 0)
        self.assertEqual(TbPerfilSeguidor.objects.count(), 0)


class DeploySyncTests(TestCase):

    def test_tabelas_sociais_sao_memoria_nunca_conteudo(self):
        """Garante o contrato do deploy: curtida/seguidor entram em MEMORY_MODELS
        e JAMAIS em CONTENT_MODELS (senão um sync de catálogo apagaria o social)."""
        from home import deploy_sync
        for nome in ('TbPerfilCurtida', 'TbPerfilSeguidor'):
            self.assertIn(nome, deploy_sync.MEMORY_MODELS)
            self.assertNotIn(nome, deploy_sync.CONTENT_MODELS)
