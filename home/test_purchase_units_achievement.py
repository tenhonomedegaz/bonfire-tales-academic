from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from home.conquistas import conceder_conquista
from home.models import (TbConquista, TbCosmetico, TbEventoConquista, TbItemMundano,
                         TbPersonagemItem, TbTransacao, TbUsuarioConquista,
                         TbUsuarioCosmetico)
from home.test_ficha_v2_onda_c import _MercadoBase
from home.views import _preco_em_pc


class PurchaseUnitsAchievementTests(_MercadoBase):
    def _rule(self, item, *, operator='gte', target=2):
        definition = {
            'schema_version': 1, 'metric': 'items_purchased_units',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'items': [{'catalog': 'mundano', 'id': item.pk}]},
            'operator': operator, 'target': target,
        }
        reward = TbCosmetico.objects.create(
            slug='badge-unidades-compra', nome='Unidades compradas',
            tipo='badge', origem='conquista')
        rule = TbConquista(slug='unidades-compradas', nome='Unidades compradas',
                          criterio='automatico', criterio_json=definition,
                          recompensa=reward)
        rule.full_clean()
        rule.save()
        return rule

    def _buy(self, character, item, quantity):
        self.client.force_login(character.dono)
        response = self.client.post(
            reverse('personagem_comprar_item', args=[character.pk]),
            {'item': item.slug, 'qtd': quantity}, **self.AJAX)
        self.assertTrue(response.json()['ok'], response.content)
        return TbTransacao.objects.filter(tipo='compra').latest('pk')

    def test_paid_units_threshold_refund_and_repurchase(self):
        char = self._char('purchase-units')
        item = self._item_mundano_com_preco()
        rule = self._rule(item)
        first = self._buy(char, item, 2)
        fact = TbEventoConquista.objects.get(tipo='item_purchased')
        self.assertEqual(fact.payload_json['quantidade'], 2)
        grant = TbUsuarioConquista.objects.get(user=char.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['total'], 2)
        self.assertEqual(grant.evidencia_json['transacao_ids'], [first.pk])
        self.assertEqual(grant.evidencia_json['evento_ids'], [str(fact.pk)])
        self.assertEqual(grant.definicao_json, rule.criterio_json)
        possession = TbUsuarioCosmetico.objects.get(user=char.dono,
                                                    cosmetico=rule.recompensa)
        self.assertIsNone(possession.suspenso_em)

        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[char.pk, first.pk]))
        grant.refresh_from_db()
        possession.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(possession.suspenso_em)
        second = self._buy(char, item, 2)
        grant.refresh_from_db()
        possession.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertIsNone(possession.suspenso_em)
        self.assertEqual(grant.evidencia_json['transacao_ids'], [second.pk])
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=char.dono, conquista=rule).count(), 1)

    def test_strict_operator_and_manual_grant_survive_refund(self):
        char = self._char('purchase-units-strict')
        item = self._item_mundano_com_preco()
        rule = self._rule(item, operator='gt', target=2)
        first = self._buy(char, item, 2)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=char.dono, conquista=rule).exists())
        second = self._buy(char, item, 1)
        grant = TbUsuarioConquista.objects.get(user=char.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['total'], 3)
        staff = get_user_model().objects.create_superuser(
            'units-staff', 'units@example.invalid', 'x')
        self.assertFalse(conceder_conquista(char.dono, rule, por=staff))
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[char.pk, second.pk]))
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.concedida_por_id, staff.pk)
        self.assertTrue(TbTransacao.objects.filter(pk=first.pk, revertida=False).exists())

    def test_two_purchases_recompute_units_after_one_refund(self):
        char = self._char('purchase-units-partial')
        item = self._item_mundano_com_preco()
        rule = self._rule(item, target=3)
        first = self._buy(char, item, 2)
        second = self._buy(char, item, 1)
        grant = TbUsuarioConquista.objects.get(user=char.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['total'], 3)
        self.client.post(reverse('personagem_reembolsar_compra',
                                 args=[char.pk, second.pk]))
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbTransacao.objects.filter(pk=first.pk, revertida=False).exists())
        self._buy(char, item, 1)
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['total'], 3)
        self.assertNotIn(second.pk, grant.evidencia_json['transacao_ids'])

    def test_other_catalog_identity_does_not_count(self):
        char = self._char('purchase-units-filter')
        item = self._item_mundano_com_preco()
        other = next(candidate for candidate in TbItemMundano.objects.exclude(pk=item.pk)
                     if _preco_em_pc(candidate.preco) is not None)
        rule = self._rule(item, target=2)
        self._buy(char, other, 2)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=char.dono, conquista=rule).exists())
        self._buy(char, item, 2)
        grant = TbUsuarioConquista.objects.get(user=char.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['total'], 2)
        self.assertEqual(len(grant.evidencia_json['transacao_ids']), 1)

    def test_traceable_legacy_units_replay_preview_and_idempotence(self):
        char = self._char('purchase-units-legacy')
        item = self._item_mundano_com_preco()
        rule = self._rule(item)
        inventory = TbPersonagemItem.objects.create(
            id_personagem=char, id_item_mundano=item,
            nome=item.nome, qtd=2, origem_tipo='compra')
        purchase = TbTransacao.objects.create(
            id_personagem=char, tipo='compra', valor_pc=-100,
            saldo_pc=char.carteira_pc,
            detalhes_json={'catalogo': 'mundano', 'catalogo_id': item.pk,
                           'inventario_id': inventory.pk, 'qtd': 2})
        call_command('reprocessar_primeira_compra', user_id=char.dono_id)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=char.dono, conquista=rule).exists())
        call_command('reprocessar_primeira_compra', apply=True, user_id=char.dono_id)
        call_command('reprocessar_primeira_compra', apply=True, user_id=char.dono_id)
        self.assertEqual(TbEventoConquista.objects.filter(tipo='item_purchased').count(), 1)
        grant = TbUsuarioConquista.objects.get(user=char.dono, conquista=rule)
        self.assertEqual(grant.evidencia_json['total'], 2)
        self.assertEqual(grant.evidencia_json['transacao_ids'], [purchase.pk])

    def test_award_failure_reverts_paid_purchase_and_fact(self):
        char = self._char('purchase-units-atomic')
        item = self._item_mundano_com_preco()
        self._rule(item, target=1)
        before = char.carteira_pc
        self.client.force_login(char.dono)
        with patch('home.conquistas.conceder_conquista',
                   side_effect=RuntimeError('award unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('personagem_comprar_item', args=[char.pk]),
                                 {'item': item.slug, 'qtd': 1}, **self.AJAX)
        char.refresh_from_db()
        self.assertEqual(char.carteira_pc, before)
        self.assertFalse(TbTransacao.objects.filter(tipo='compra').exists())
        self.assertFalse(TbEventoConquista.objects.filter(tipo='item_purchased').exists())

    def test_malformed_or_ambiguous_item_identity_is_rejected(self):
        char = self._char('purchase-units-validation')
        item = self._item_mundano_com_preco()
        rule = self._rule(item)
        for invalid in (
            {**rule.criterio_json, 'operator': 'eval'},
            {**rule.criterio_json, 'operator': ['gte']},
            {**rule.criterio_json, 'target': True},
            {**rule.criterio_json, 'filters': {'items': [
                {'catalog': 'mundano', 'id': item.pk}] * 2}},
            {**rule.criterio_json, 'filters': {'items': [
                {'catalog': 'mundano', 'id': str(item.pk)}]}},
            {**rule.criterio_json, 'filters': {'items': [
                {'catalog': ['mundano'], 'id': item.pk}]}},
        ):
            rule.criterio_json = invalid
            with self.assertRaises(ValidationError):
                rule.full_clean()
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=char.dono, conquista=rule).exists())

    def test_staff_form_explains_configured_operator_and_item_identity(self):
        staff = get_user_model().objects.create_superuser(
            'units-admin', 'units-admin@example.invalid', 'x')
        self.client.force_login(staff)
        response = self.client.get(reverse('admin:home_tbconquista_add'))
        self.assertContains(response, 'items_purchased_units')
        self.assertContains(response, 'IDs reais do catálogo')
        self.assertContains(response, 'gt ou gte')
