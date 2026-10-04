import json

from django.urls import reverse

from home.character_history import capture_build, register_revision, revision_status
from home.models import (
    TbItemMundano,
    TbPersonagem,
    TbPersonagemAventura,
    TbPersonagemItem,
    TbTransacao,
)
from home.test_criador import _CriadorBase


class CharacterHistoryTests(_CriadorBase):
    def setUp(self):
        self.owner = self._novo_usuario('history-owner')
        self.staff = self._novo_usuario('history-staff', staff=True)
        response = self._post_criar(self.owner, self._payload('guerreiro'))
        self.assertEqual(response.status_code, 200, response.content)
        self.personagem = TbPersonagem.objects.get(pk=response.json()['id'])

    def _levelup_revision(self):
        p = self.personagem
        snapshot = capture_build(p)
        pc = p.classes.get(principal=True)
        pc.nivel = 2
        pc.save(update_fields=['nivel'])
        p.nivel = 2
        p.save(update_fields=['nivel', 'atualizado_em'])
        return register_revision(
            p, tipo='level_up', snapshot=snapshot, user=self.owner,
            descricao='Teste de level-up', nivel_antes=1, nivel_depois=2)

    def test_dono_reverte_levelup_enquanto_nao_jogou_nova_mesa(self):
        revision = self._levelup_revision()
        self.client.force_login(self.owner)
        response = self.client.post(reverse(
            'personagem_reverter_revisao', args=[self.personagem.pk, revision.pk]))
        self.assertEqual(response.status_code, 302)
        self.personagem.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(self.personagem.nivel, 1)
        self.assertTrue(revision.revertida)

    def test_nova_mesa_bloqueia_rollback_do_jogador(self):
        revision = self._levelup_revision()
        TbPersonagemAventura.objects.create(
            id_personagem=self.personagem, nome_aventura='Mesa posterior',
            qtd_aventuras=1, nivel_no_lancamento=2, criado_por=self.staff)
        self.personagem.aventuras = int(self.personagem.aventuras or 0) + 1
        self.personagem.save(update_fields=['aventuras', 'atualizado_em'])
        self.client.force_login(self.owner)
        self.client.post(reverse(
            'personagem_reverter_revisao', args=[self.personagem.pk, revision.pk]))
        self.personagem.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(self.personagem.nivel, 2)
        self.assertFalse(revision.revertida)

    def test_recompensa_da_comunidade_nao_bloqueia_rollback(self):
        revision = self._levelup_revision()
        TbPersonagemAventura.objects.create(
            id_personagem=self.personagem, nome_aventura='Recompensa da comunidade',
            qtd_aventuras=1, origem='recompensa_comunidade')
        self.personagem.aventuras = int(self.personagem.aventuras or 0) + 1
        self.personagem.save(update_fields=['aventuras', 'atualizado_em'])

        allowed, message = revision_status(self.personagem, revision)

        self.assertTrue(allowed, message)

    def test_legacy_adventure_after_community_reward_still_blocks_rollback(self):
        revision = self._levelup_revision()
        TbPersonagemAventura.objects.create(
            id_personagem=self.personagem, nome_aventura='Recompensa da comunidade',
            qtd_aventuras=1, origem='recompensa_comunidade')
        self.personagem.aventuras = int(self.personagem.aventuras or 0) + 2
        self.personagem.save(update_fields=['aventuras', 'atualizado_em'])

        allowed, _ = revision_status(self.personagem, revision)

        self.assertFalse(allowed)

    def test_staff_recria_nivel_um_preservando_progressao_e_economia(self):
        item = TbItemMundano.objects.first()
        bought = TbPersonagemItem.objects.create(
            id_personagem=self.personagem, id_item_mundano=item, nome=item.nome,
            qtd=1, origem_tipo='compra')
        self.personagem.aventuras = 12
        self.personagem.carteira_pc = 43210
        self.personagem.braseiros = 17
        self.personagem.save(update_fields=[
            'aventuras', 'carteira_pc', 'braseiros', 'atualizado_em'])

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('personagem_recriar_nivel_1', args=[self.personagem.pk]),
            data=json.dumps(self._payload('mago')),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.personagem.refresh_from_db()
        self.assertEqual(self.personagem.nivel, 1)
        self.assertEqual(self.personagem.classes.get(principal=True).id_classe.slug, 'mago')
        self.assertEqual(self.personagem.aventuras, 12)
        self.assertEqual(self.personagem.carteira_pc, 43210)
        self.assertEqual(self.personagem.braseiros, 17)
        self.assertTrue(self.personagem.inventario.filter(pk=bought.pk).exists())
        self.assertTrue(self.personagem.revisoes_build.filter(tipo='nivel_1').exists())

    def test_compra_auditavel_pode_ser_reembolsada_antes_da_proxima_mesa(self):
        item = TbItemMundano.objects.first()
        inventory = TbPersonagemItem.objects.create(
            id_personagem=self.personagem, id_item_mundano=item, nome=item.nome,
            qtd=2, origem_tipo='compra')
        self.personagem.carteira_pc = 800
        self.personagem.save(update_fields=['carteira_pc', 'atualizado_em'])
        purchase = TbTransacao.objects.create(
            id_personagem=self.personagem, tipo='compra', descricao='Compra de teste',
            valor_pc=-200, saldo_pc=800,
            detalhes_json={
                'catalogo': 'mundano', 'catalogo_id': item.pk,
                'inventario_id': inventory.pk, 'qtd': 2,
                'aventuras_no_momento': int(self.personagem.aventuras or 0),
            })

        self.client.force_login(self.owner)
        response = self.client.post(reverse(
            'personagem_reembolsar_compra', args=[self.personagem.pk, purchase.pk]))
        self.assertEqual(response.status_code, 302)
        self.personagem.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(self.personagem.carteira_pc, 1000)
        self.assertTrue(purchase.revertida)
        self.assertFalse(self.personagem.inventario.filter(pk=inventory.pk).exists())
