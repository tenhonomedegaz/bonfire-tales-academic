"""MM theme redemption and audited compensation using the existing wallet ledger."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .cosmetic_entitlements import has_permanent_cosmetic
from .models import (CosmeticCheckoutOffer, CosmeticMMRedemption,
                     TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)


@transaction.atomic
def redeem_theme_mm(user_id, slug, request_key):
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if not user.is_active:
        raise ValueError('Conta inativa.')
    previous = CosmeticMMRedemption.objects.filter(
        user=user, request_key=request_key).select_related('cosmetico').first()
    if previous:
        if previous.cosmetico.slug != slug or previous.reversed_at:
            raise ValueError('Solicitação já utilizada para outro resgate.')
        return previous, False
    offer = CosmeticCheckoutOffer.objects.select_related('cosmetico').filter(
        cosmetico__slug=slug, cosmetico__tipo='tema', cosmetico__origem='loja_mm',
        cosmetico__ativo=True, active=True, demonstration=False,
    ).first()
    if not offer or offer.cosmetico.preco <= 0:
        raise ValueError('Tema indisponível para resgate em MM.')
    cosmetic = offer.cosmetico
    if has_permanent_cosmetic(user, cosmetic) or TbUsuarioCosmetico.objects.filter(
            user=user, cosmetico=cosmetic, suspenso_em__isnull=True,
        ).exclude(origem__startswith='colaborador').exists():
        raise ValueError('Tema já pertence à sua conta.')
    profile = UserProfile.objects.select_for_update().get(user=user)
    cost = int(cosmetic.preco)
    if int(profile.moedas_mestragem or 0) < cost:
        raise ValueError('Saldo MM insuficiente.')
    profile.moedas_mestragem -= cost
    profile.save(update_fields=['moedas_mestragem'])
    debit = TbTransacaoMestre.objects.create(
        mestre=user, tipo='resgate', descricao=f'Tema {slug} (MM)',
        valor_mm=-cost, saldo_mm=profile.moedas_mestragem,
    )
    inventory, created_inventory = TbUsuarioCosmetico.objects.get_or_create(
        user=user, cosmetico=cosmetic, defaults={'origem': 'compra_mm'},
    )
    receipt = CosmeticMMRedemption.objects.create(
        user=user, cosmetico=cosmetic, request_key=request_key,
        cost_mm=cost, transaction=debit,
        prior_inventory_existed=not created_inventory,
        prior_inventory_origin=inventory.origem if not created_inventory else '',
        prior_inventory_suspended_at=inventory.suspenso_em if not created_inventory else None,
    )
    if inventory.origem.startswith('colaborador') or inventory.suspenso_em:
        inventory.origem = 'compra_mm'
        inventory.suspenso_em = None
        inventory.save(update_fields=['origem', 'suspenso_em'])
    return receipt, True


@transaction.atomic
def reverse_theme_mm(redemption_id):
    receipt = CosmeticMMRedemption.objects.select_related('user', 'cosmetico').get(
        pk=redemption_id)
    user = get_user_model().objects.select_for_update().get(pk=receipt.user_id)
    receipt = CosmeticMMRedemption.objects.select_for_update().get(pk=redemption_id)
    if receipt.reversed_at:
        return receipt, False
    debit = receipt.transaction
    if (debit.mestre_id != user.pk or debit.tipo != 'resgate'
            or debit.valor_mm != -receipt.cost_mm):
        raise ValueError('Recibo e débito MM divergentes; requer revisão manual.')
    profile = UserProfile.objects.select_for_update().get(user=user)
    profile.moedas_mestragem = int(profile.moedas_mestragem or 0) + receipt.cost_mm
    profile.save(update_fields=['moedas_mestragem'])
    refund = TbTransacaoMestre.objects.create(
        mestre=user, tipo='ajuste', descricao=f'Estorno de tema MM #{receipt.pk}',
        valor_mm=receipt.cost_mm, saldo_mm=profile.moedas_mestragem,
    )
    receipt.reversed_at = timezone.now()
    receipt.reversal_transaction = refund
    receipt.save(update_fields=['reversed_at', 'reversal_transaction'])
    inventory = TbUsuarioCosmetico.objects.select_for_update().filter(
        user=user, cosmetico_id=receipt.cosmetico_id, origem='compra_mm',
        suspenso_em__isnull=True,
    ).first()
    if inventory:
        if receipt.prior_inventory_existed:
            inventory.origem = receipt.prior_inventory_origin
            inventory.suspenso_em = receipt.prior_inventory_suspended_at
            inventory.save(update_fields=['origem', 'suspenso_em'])
        elif not has_permanent_cosmetic(user, receipt.cosmetico):
            inventory.suspenso_em = timezone.now()
            inventory.save(update_fields=['suspenso_em'])
    return receipt, True
