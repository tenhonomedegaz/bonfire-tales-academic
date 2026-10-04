"""Direitos de cosméticos comprados, independentes de concessões temporárias."""

from django.db import transaction
from django.utils import timezone

from .models import CosmeticCheckoutPurchase, TbUsuarioCosmetico


def has_permanent_cosmetic(user, cosmetico):
    """Consulta por chave de catálogo; uma suspensão do inventário não revoga compra."""
    if not getattr(user, 'pk', None):
        return False
    return CosmeticCheckoutPurchase.objects.filter(
        beneficiary=user, cosmetico=cosmetico, granted_at__isnull=False,
    ).exists()


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
