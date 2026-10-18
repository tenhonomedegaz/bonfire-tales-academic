"""Lifetime Mestre Ouro grants backed by the first proven MM purchase."""

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (MestreOuroDireito, MestreOuroRevisao, TbRecompensaMestre,
                     TbTransacaoMestre, TbCosmetico, TbUsuarioCosmetico, UserProfile)


GOLD_COSMETIC_SLUGS = ('titulo-mestre-ouro', 'moldura-mestre-ouro')
CHARACTER_SLOT_PRICE_MM = 5000


def _grant_cosmetics(user):
    """Add lifetime inventory once; never replace the player's equipped choices."""
    cosmetics = list(TbCosmetico.objects.filter(
        slug__in=GOLD_COSMETIC_SLUGS, origem='mestre_ouro', ativo=True,
    ))
    if {item.slug for item in cosmetics} != set(GOLD_COSMETIC_SLUGS):
        raise ValueError('Mestre Ouro cosmetics are not installed')
    for item in cosmetics:
        TbUsuarioCosmetico.objects.get_or_create(
            user=user, cosmetico=item, defaults={'origem': 'mestre_ouro'},
        )


def _purchases(user_id):
    return list(TbTransacaoMestre.objects.filter(
        mestre_id=user_id, tipo='assinatura', valor_mm__lt=0,
    ).order_by('criado_em', 'pk')[:2])


def _has_slot_redemption_without_right(user_id):
    return TbTransacaoMestre.objects.filter(
        mestre_id=user_id, tipo='resgate', valor_mm__lt=0,
        descricao__icontains='Slot permanente de personagem',
    ).exists()


def has_unreconciled_mestre_ouro_history(user_id, profile=None):
    """A past subscription/charge must be reviewed before a new slot debit."""
    if MestreOuroDireito.objects.filter(user_id=user_id).exists():
        return False
    if profile is None:
        profile = UserProfile.objects.filter(user_id=user_id).first()
    return bool(
        (profile and profile.mestre_ouro_ativo)
        or _purchases(user_id)
        or _has_slot_redemption_without_right(user_id)
        or TbTransacaoMestre.objects.filter(
            mestre_id=user_id, tipo='mensalidade', valor_mm__lt=0).exists()
        or MestreOuroRevisao.objects.filter(user_id=user_id).exists()
    )


@transaction.atomic
def buy_character_slot_with_mm(user_id):
    """Reuse the lifetime right; a locked account prevents two debits on replay."""
    from .permissions import is_mestre

    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if not user.is_active:
        raise ValueError('not eligible for MM redemption')
    existing = MestreOuroDireito.objects.filter(user=user).first()
    if existing:
        return existing, False
    if not is_mestre(user):
        raise ValueError('not eligible for MM redemption')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
    if has_unreconciled_mestre_ouro_history(user_id, profile):
        raise ValueError('legacy Mestre Ouro history requires review')
    balance = int(profile.moedas_mestragem or 0)
    if balance < CHARACTER_SLOT_PRICE_MM:
        raise ValueError('insufficient MM balance')
    _grant_cosmetics(user)
    profile.moedas_mestragem = balance - CHARACTER_SLOT_PRICE_MM
    profile.save(update_fields=['moedas_mestragem'])
    purchase = TbTransacaoMestre.objects.create(
        mestre=user, tipo='resgate', descricao='Slot permanente de personagem (Mestre Ouro)',
        valor_mm=-CHARACTER_SLOT_PRICE_MM, saldo_mm=profile.moedas_mestragem,
    )
    grant = MestreOuroDireito.objects.create(
        user=user, primeira_compra=purchase, adquirido_em=purchase.criado_em,
    )
    return grant, True


@transaction.atomic
def reconcile_mestre_ouro(user_id):
    """Grant once for one proven purchase, or retain an ambiguity for review."""
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
    existing = MestreOuroDireito.objects.filter(user=user).first()
    if existing:
        _grant_cosmetics(user)
        return existing, 'already_granted'
    purchases = _purchases(user_id)
    if _has_slot_redemption_without_right(user_id):
        MestreOuroRevisao.objects.update_or_create(
            user=user, defaults={'motivo': 'slot_redemption_without_right'},
        )
        return None, 'review_required'
    if len(purchases) == 1:
        first = purchases[0]
        grant = MestreOuroDireito.objects.create(
            user=user, primeira_compra=first, adquirido_em=first.criado_em,
        )
        _grant_cosmetics(user)
        profile.mestre_ouro_ativo = True
        profile.mestre_ouro_proximo_pgto = None
        profile.save(update_fields=['mestre_ouro_ativo', 'mestre_ouro_proximo_pgto'])
        MestreOuroRevisao.objects.filter(user=user).delete()
        return grant, 'granted'
    monthly = TbTransacaoMestre.objects.filter(
        mestre=user, tipo='mensalidade', valor_mm__lt=0,
    ).exists()
    if len(purchases) > 1 or profile.mestre_ouro_ativo or monthly:
        reason = ('multiple_first_purchases' if len(purchases) > 1
                  else 'legacy_status_without_purchase' if profile.mestre_ouro_ativo
                  else 'monthly_charge_without_purchase')
        MestreOuroRevisao.objects.update_or_create(user=user, defaults={'motivo': reason})
        return None, 'review_required'
    return None, 'no_purchase'


@transaction.atomic
def buy_mestre_ouro_lifetime(user_id, offer_id):
    """Single approved-price debit and lifetime grant in the same transaction."""
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if not user.is_active:
        raise ValueError('inactive account')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
    offer = TbRecompensaMestre.objects.select_for_update().get(pk=offer_id)
    if offer.tipo != 'assinatura' or not offer.ativo:
        raise ValueError('Mestre Ouro offer unavailable')
    existing = MestreOuroDireito.objects.filter(user=user).first()
    if existing:
        _grant_cosmetics(user)
        return existing, False
    if (_purchases(user_id) or profile.mestre_ouro_ativo
            or _has_slot_redemption_without_right(user_id)):
        grant, result = reconcile_mestre_ouro(user_id)
        if result in ('granted', 'already_granted'):
            return grant, False
        raise ValueError('legacy Mestre Ouro history requires review')
    if (not offer.preco_vitalicio_aprovado_mm or offer.preco_mm <= 0
            or offer.preco_mm != offer.preco_vitalicio_aprovado_mm):
        raise ValueError('lifetime Mestre Ouro price is not approved')
    if (profile.moedas_mestragem or 0) < offer.preco_mm:
        raise ValueError('insufficient MM balance')
    profile.moedas_mestragem -= offer.preco_mm
    profile.mestre_ouro_ativo = True
    profile.mestre_ouro_proximo_pgto = None
    profile.save(update_fields=['moedas_mestragem', 'mestre_ouro_ativo',
                                'mestre_ouro_proximo_pgto'])
    purchase = TbTransacaoMestre.objects.create(
        mestre=user, tipo='assinatura', descricao='Mestre Ouro (compra vitalícia)',
        valor_mm=-offer.preco_mm, saldo_mm=profile.moedas_mestragem,
    )
    grant = MestreOuroDireito.objects.create(
        user=user, primeira_compra=purchase, adquirido_em=purchase.criado_em,
    )
    _grant_cosmetics(user)
    return grant, True
