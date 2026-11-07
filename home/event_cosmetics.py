"""Resgate de cosméticos de evento com saldo de braseiros do personagem."""

from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .cosmetic_entitlements import has_permanent_cosmetic
from .models import (EventCosmeticOffer, EventCosmeticRedemption,
                     TbEventoConquista, TbPersonagem, TbUsuarioCosmetico)


def event_cosmetic_fact_fields(redemption):
    """Stable event identity and original redemption snapshot for new and old claims."""
    return {
        'origem': 'site_event_cosmetic',
        'chave_origem': f'resgate:{redemption.request_id}',
        'tipo': 'event_cosmetic_redeemed',
        'conta_id': redemption.user_id,
        'personagem_id': redemption.character_id,
        'agregado_id': redemption.pk,
        'ocorrido_em': redemption.created_at,
        'payload_json': {
            'offer_id': redemption.offer_id,
            'cosmetic_id': redemption.cosmetico_id,
            'cost_braseiros': redemption.cost_braseiros,
        },
    }


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
            same_character = True
            if previous.cost_braseiros:
                try:
                    same_character = int(character_id) == previous.character_id
                except (TypeError, ValueError):
                    same_character = False
            if (previous.user_id != user.pk or previous.offer_id != offer_id
                    or previous.cost_braseiros != price_seen or not same_character):
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
        # O fato nasce junto com o débito e o direito. Uma falha aqui desfaz os
        # três registros, permitindo reprocessar a mesma solicitação com segurança.
        TbEventoConquista.objects.create(**event_cosmetic_fact_fields(redemption))
        return redemption, True
