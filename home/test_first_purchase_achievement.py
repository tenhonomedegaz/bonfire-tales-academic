from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from home.conquistas import conquistas_do_usuario, conceder_conquista
from home.models import TbConquista, TbCosmetico, TbTransacao, TbUsuarioConquista, TbUsuarioCosmetico
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
