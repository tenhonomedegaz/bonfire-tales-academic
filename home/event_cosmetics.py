"""Resgate de cosméticos de evento com saldo de braseiros do personagem."""

from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .cosmetic_entitlements import has_permanent_cosmetic
from .models import (EventCosmeticOffer, EventCosmeticRedemption,
                     TbPersonagem, TbUsuarioCosmetico)


def redeem_event_cosmetic(user, offer_id, character_id, request_id, quoted_cost):
    """Retorna (resgate, criado); uma tentativa repetida nunca debita outra vez."""
    try:
        operation = UUID(str(request_id))
        offer_id = int(offer_id)
        price_seen = int(quoted_cost)
    except (TypeError, ValueError, AttributeError):
        raise ValueError('pedido_invalido')

    with transaction.atomic():
        # Serializa todos os envios da mesma conta, inclusive os de personagens distintos.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = EventCosmeticRedemption.objects.filter(request_id=operation).first()
        if previous:
            if previous.user_id != user.pk:
                raise ValueError('pedido_invalido')
            return previous, False

        offer = (EventCosmeticOffer.objects.select_for_update()
                 .select_related('cosmetico').filter(pk=offer_id).first())
        now = timezone.now()
        if not offer or not offer.active or not offer.cosmetico.ativo \
                or offer.cosmetico.origem not in {'loja_braseiro', 'evento_manual'} \
                or (offer.starts_at and now < offer.starts_at) \
                or (offer.ends_at and now >= offer.ends_at):
            raise ValueError('oferta_indisponivel')
        if offer.cost_braseiros != price_seen:
            raise ValueError('preco_alterado')
        character = None
        if offer.cost_braseiros:
            try:
                character_id = int(character_id)
            except (TypeError, ValueError):
                raise ValueError('personagem_invalido')
            character = (TbPersonagem.objects.select_for_update()
                         .filter(pk=character_id, dono=user, arquivado=False).first())
            if not character:
                raise ValueError('personagem_invalido')
        inventory = (TbUsuarioCosmetico.objects.select_for_update()
                     .filter(user=user, cosmetico=offer.cosmetico).first())
        if has_permanent_cosmetic(user, offer.cosmetico) or (
                inventory and inventory.suspenso_em is None
                and not inventory.origem.startswith('colaborador')):
            raise ValueError('ja_possui')
        if character and (character.braseiros or 0) < offer.cost_braseiros:
            raise ValueError('saldo_insuficiente')

        if character:
            character.braseiros -= offer.cost_braseiros
            character.save(update_fields=['braseiros', 'atualizado_em'])
        redemption = EventCosmeticRedemption.objects.create(
            request_id=operation, offer=offer, user=user, character=character,
            cosmetico=offer.cosmetico, cost_braseiros=offer.cost_braseiros,
            balance_after=character.braseiros if character else None)
        if inventory:
            inventory.origem = f'evento:{redemption.pk}'
            inventory.suspenso_em = None
            inventory.save(update_fields=['origem', 'suspenso_em'])
        else:
            TbUsuarioCosmetico.objects.create(
                user=user, cosmetico=offer.cosmetico,
                origem=f'evento:{redemption.pk}')
        return redemption, True
