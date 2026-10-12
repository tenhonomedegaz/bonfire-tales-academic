from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from home.conquistas import conquistas_do_usuario, conceder_conquista
from home.models import (TbConquista, TbCosmetico, TbEntregaEventoConquista, TbEventoConquista,
                         TbPersonagemItem, TbTransacao, TbUsuarioConquista, TbUsuarioCosmetico)
from home.test_ficha_v2_onda_c import _MercadoBase


RULE = {'schema_version': 1, 'metric': 'items_purchased',
        'scope': 'account', 'operator': 'gte', 'target': 1}


class FirstPurchaseAchievementTests(_MercadoBase):
    def _rule(self):
        reward = TbCosmetico.objects.create(
            slug='badge-primeira-compra', nome='Comprador', tipo='badge',
            origem='conquista')
        rule = TbConquista.objects.create(
            slug='primeira-compra', nome='Primeira compra', criterio='automatico',
            criterio_json=RULE, recompensa=reward)
        rule.full_clean()
        return rule

    def _buy(self, character):
        self.client.force_login(character.dono)
        response = self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                                    {'item': self._item_mundano_com_preco().slug}, **self.AJAX)
        self.assertTrue(response.json()['ok'])
        return TbTransacao.objects.filter(tipo='compra').latest('pk')

    def test_purchase_and_refund_delivery_replay_is_idempotent(self):
        rule = self._rule()
        rule.ativo = False
        rule.save(update_fields=['ativo'])
        character = self._char('purchase-delivery')
        purchase = self._buy(character)
        fact = TbEventoConquista.objects.get(tipo='item_purchased', agregado_id=purchase.pk)
        delivery = TbEntregaEventoConquista.objects.get(evento=fact,
                                                         consumidor='conquistas_compras_v1')
        self.assertEqual(delivery.estado, 'pendente')
        rule.ativo = True
        rule.save(update_fields=['ativo'])
        call_command('processar_entregas_compra', user_id=character.dono_id)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=character.dono,
                                                             conquista=rule).exists())
        call_command('processar_entregas_compra', apply=True, user_id=character.dono_id)
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(TbUsuarioConquista.objects.filter(user=character.dono,
                                                            conquista=rule).count(), 1)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, purchase.pk]))
        refund_fact = TbEventoConquista.objects.get(tipo='item_purchase_refunded',
                                                     agregado_id=purchase.pk)
        refund_delivery = TbEntregaEventoConquista.objects.get(
            evento=refund_fact, consumidor='conquistas_compras_v1')
        self.assertEqual(refund_delivery.estado, 'pendente')
        call_command('processar_entregas_compra', apply=True, user_id=character.dono_id)
        refund_delivery.refresh_from_db()
        self.assertEqual(refund_delivery.estado, 'concluida')
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        self.assertIsNotNone(grant.revogada_em)
        call_command('processar_entregas_compra', apply=True, user_id=character.dono_id)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=character.dono,
                                                            conquista=rule).count(), 1)

    def test_purchase_delivery_failure_rolls_back_grant_and_can_retry(self):
        rule = self._rule()
        rule.ativo = False
        rule.save(update_fields=['ativo'])
        character = self._char('purchase-retry')
        purchase = self._buy(character)
        fact = TbEventoConquista.objects.get(tipo='item_purchased', agregado_id=purchase.pk)
        delivery = TbEntregaEventoConquista.objects.get(evento=fact,
                                                         consumidor='conquistas_compras_v1')
        rule.ativo = True
        rule.save(update_fields=['ativo'])
        from home.event_deliveries import process_purchase_delivery, reserve_purchase_delivery
        reservation = reserve_purchase_delivery(user_id=character.dono_id)
        self.assertEqual(reservation[0], delivery.pk)
        with patch('home.event_deliveries._avaliar_unidades_compradas',
                   side_effect=RuntimeError('test failure')):
            self.assertFalse(process_purchase_delivery(*reservation, max_attempts=1))
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'revisao')
        self.assertFalse(TbUsuarioConquista.objects.filter(user=character.dono,
                                                             conquista=rule).exists())
        call_command('processar_entregas_compra', resume_review_id=delivery.pk,
                     apply=True, user_id=character.dono_id)
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(TbUsuarioConquista.objects.filter(user=character.dono,
                                                            conquista=rule).count(), 1)

    def test_paid_purchase_refund_and_new_purchase_reactivate_one_grant(self):
        rule = self._rule()
        character = self._char('first-purchase')
        purchase = self._buy(character)
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['agregado_id'], purchase.pk)
        self.assertEqual(grant.definicao_json, RULE)
        possession = TbUsuarioCosmetico.objects.get(user=character.dono, cosmetico=rule.recompensa)
        self.assertIsNone(possession.suspenso_em)
        self.assertEqual(conquistas_do_usuario(character.dono)['obtidas_count'], 1)

        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, purchase.pk]))
        grant.refresh_from_db()
        possession.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(possession.suspenso_em)
        self.assertEqual(conquistas_do_usuario(character.dono)['obtidas_count'], 0)

        second = self._buy(character)
        grant.refresh_from_db()
        possession.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertIsNone(possession.suspenso_em)
        self.assertEqual(grant.evidencia_json['agregado_id'], second.pk)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=character.dono,
                                                           conquista=rule).count(), 1)

    def test_other_active_purchase_keeps_grant_after_refund(self):
        rule = self._rule()
        character = self._char('two-purchases')
        first = self._buy(character)
        second = self._buy(character)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, first.pk]))
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['agregado_id'], second.pk)
        self.assertTrue(TbTransacao.objects.filter(pk=second.pk, revertida=False).exists())

    def test_manual_grant_and_other_reward_origin_survive_refund(self):
        rule = self._rule()
        character = self._char('staff-purchase')
        staff = get_user_model().objects.create_superuser('staff-purchase', 'staff@example.invalid', 'x')
        conceder_conquista(character.dono, rule, por=staff)
        possession = TbUsuarioCosmetico.objects.get(user=character.dono, cosmetico=rule.recompensa)
        possession.origem = 'staff'
        possession.save(update_fields=['origem'])
        purchase = self._buy(character)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, purchase.pk]))
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        possession.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertIsNone(possession.suspenso_em)

    def test_another_achievement_can_reactivate_suspended_reward(self):
        rule = self._rule()
        character = self._char('second-reward-source')
        purchase = self._buy(character)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, purchase.pk]))
        other = TbConquista.objects.create(slug='outro-premio', nome='Outro prêmio',
                                            recompensa=rule.recompensa)
        self.assertTrue(conceder_conquista(character.dono, other))
        possession = TbUsuarioCosmetico.objects.get(user=character.dono,
                                                    cosmetico=rule.recompensa)
        self.assertIsNone(possession.suspenso_em)
        self.assertEqual(possession.origem, 'conquista:outro-premio')

    def test_staff_regrant_of_automatic_award_survives_refund(self):
        rule = self._rule()
        character = self._char('manual-override')
        purchase = self._buy(character)
        staff = get_user_model().objects.create_superuser('manual-override-staff',
                                                           'override@example.invalid', 'x')
        self.assertFalse(conceder_conquista(character.dono, rule, por=staff))
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[character.pk, purchase.pk]))
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        self.assertEqual(grant.concedida_por_id, staff.pk)
        self.assertIsNone(grant.revogada_em)

    def test_invalid_rule_and_failed_award_roll_back_purchase(self):
        rule = self._rule()
        rule.criterio_json = {**RULE, 'target': 0}
        with self.assertRaises(ValidationError):
            rule.full_clean()
        rule.criterio_json = RULE
        character = self._char('failed-award')
        self.client.force_login(character.dono)
        with patch('home.conquistas.conceder_conquista', side_effect=RuntimeError('award failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('personagem_comprar_item', args=[character.pk]),
                                 {'item': self._item_mundano_com_preco().slug}, **self.AJAX)
        self.assertFalse(TbTransacao.objects.filter(tipo='compra').exists())
        self.assertFalse(TbEntregaEventoConquista.objects.filter(
            consumidor='conquistas_compras_v1').exists())

    def test_legacy_ledger_replay_is_previewable_and_idempotent(self):
        rule = self._rule()
        character = self._char('legacy-first-purchase')
        item = self._item_mundano_com_preco()
        inventory = TbPersonagemItem.objects.create(
            id_personagem=character, id_item_mundano=item,
            nome=item.nome, qtd=1, origem_tipo='compra')
        purchase = TbTransacao.objects.create(
            id_personagem=character, tipo='compra', valor_pc=-100,
            saldo_pc=character.carteira_pc,
            detalhes_json={'catalogo': 'mundano', 'catalogo_id': item.pk,
                           'inventario_id': inventory.pk, 'qtd': 1})
        TbTransacao.objects.create(id_personagem=character, tipo='compra',
                                   valor_pc=-10, saldo_pc=character.carteira_pc,
                                   detalhes_json={})
        call_command('reprocessar_primeira_compra', user_id=character.dono_id)
        self.assertFalse(TbEventoConquista.objects.filter(tipo='item_purchased').exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=character.dono).exists())
        call_command('reprocessar_primeira_compra', apply=True, user_id=character.dono_id)
        call_command('reprocessar_primeira_compra', apply=True, user_id=character.dono_id)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='item_purchased').count(), 1)
        grant = TbUsuarioConquista.objects.get(user=character.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['agregado_id'], purchase.pk)
