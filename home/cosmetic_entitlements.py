"""Direitos de cosméticos comprados, independentes de concessões temporárias."""

from django.db import transaction
from django.utils import timezone

from .models import (CosmeticCheckoutPurchase, CosmeticMMRedemption, EventCosmeticRedemption,
                     TbUsuarioCosmetico)


def has_permanent_cosmetic(user, cosmetico):
    """Consulta por chave de catálogo; uma suspensão do inventário não revoga compra."""
    if not getattr(user, 'pk', None):
        return False
    return (CosmeticCheckoutPurchase.objects.filter(
        beneficiary=user, cosmetico=cosmetico, granted_at__isnull=False,
    ).exists() or EventCosmeticRedemption.objects.filter(
        user=user, cosmetico=cosmetico).exists() or CosmeticMMRedemption.objects.filter(
        user=user, cosmetico=cosmetico, reversed_at__isnull=True).exists())


def _permanent_sources(user):
    """Read all active permanent sources once inside an explicit profile read."""
    from .cosmetics import _cosmetic_read_memo
    def load():
        return {
            'paid': dict(CosmeticCheckoutPurchase.objects.filter(
                beneficiary=user, granted_at__isnull=False, cosmetico__ativo=True,
            ).values_list('cosmetico__slug', 'cosmetico__tipo')),
            'event': dict(EventCosmeticRedemption.objects.filter(
                user=user, cosmetico__ativo=True,
            ).values_list('cosmetico__slug', 'cosmetico__tipo')),
            'mm': dict(CosmeticMMRedemption.objects.filter(
                user=user, reversed_at__isnull=True, cosmetico__ativo=True,
            ).values_list('cosmetico__slug', 'cosmetico__tipo')),
        }
    return _cosmetic_read_memo(('permanent_sources', user.pk), load)


def permanent_cosmetic_slugs(user, tipo=None):
    """Paid, granted catalog slugs; independent of a suspendable inventory row."""
    if not getattr(user, 'pk', None):
        return set()
    from .cosmetics import _READ_CONTEXT
    if _READ_CONTEXT.get() is not None:
        return {slug for records in _permanent_sources(user).values()
                for slug, kind in records.items() if not tipo or kind == tipo}
    purchases = CosmeticCheckoutPurchase.objects.filter(
        beneficiary=user, granted_at__isnull=False, cosmetico__ativo=True,
    )
    if tipo:
        purchases = purchases.filter(cosmetico__tipo=tipo)
    event_redemptions = EventCosmeticRedemption.objects.filter(
        user=user, cosmetico__ativo=True)
    if tipo:
        event_redemptions = event_redemptions.filter(cosmetico__tipo=tipo)
    mm = CosmeticMMRedemption.objects.filter(
        user=user, cosmetico__ativo=True, reversed_at__isnull=True)
    if tipo:
        mm = mm.filter(cosmetico__tipo=tipo)
    return (set(purchases.values_list('cosmetico__slug', flat=True)) |
            set(event_redemptions.values_list('cosmetico__slug', flat=True)) |
            set(mm.values_list('cosmetico__slug', flat=True)))


def grant_paid_purchase(purchase):
    """Concede uma vez sob bloqueio do pedido e preserva a origem paga."""
    with transaction.atomic():
        purchase = CosmeticCheckoutPurchase.objects.select_for_update().get(pk=purchase.pk)
        if purchase.granted_at:
            return False
        inventory, _ = TbUsuarioCosmetico.objects.get_or_create(
            user=purchase.beneficiary, cosmetico=purchase.cosmetico,
            defaults={'origem': 'compra_asaas'},
        )
        if inventory.suspenso_em or inventory.origem != 'compra_asaas':
            inventory.suspenso_em = None
            inventory.origem = 'compra_asaas'
            inventory.save(update_fields=['suspenso_em', 'origem'])
        purchase.granted_at = timezone.now()
        purchase.save(update_fields=['granted_at'])
        return True
