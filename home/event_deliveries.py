"""Entrega local recuperável de fatos canônicos para conquistas."""

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .conquistas import (avaliar_aventuras_jogadas, avaliar_inicio_classe_evento,
                        avaliar_nivel_personagem, avaliar_primeira_cronica_evento,
                        avaliar_primeira_ficha_evento, avaliar_quests_categorizadas,
                        _avaliar_primeira_compra, _avaliar_unidades_compradas)
from .models import TbEntregaEventoConquista, TbEventoConquista


CREATION_CONSUMER = 'conquistas_criacao_v1'
ADVENTURE_CONSUMER = 'conquistas_aventuras_v1'
STORY_CONSUMER = 'conquistas_cronicas_v1'
LEVEL_CONSUMER = 'conquistas_nivel_v1'
PURCHASE_CONSUMER = 'conquistas_compras_v1'


def enqueue_purchase_event(evento):
    if evento.origem != 'site_market' or evento.tipo not in (
            'item_purchased', 'item_purchase_refunded'):
        return None
    entrega, _ = TbEntregaEventoConquista.objects.get_or_create(
        evento=evento, consumidor=PURCHASE_CONSUMER)
    return entrega


def enqueue_existing_purchase_events(*, user_id=None):
    facts = TbEventoConquista.objects.filter(
        origem='site_market', tipo__in=('item_purchased', 'item_purchase_refunded'))
    if user_id is not None:
        facts = facts.filter(conta_id=user_id)
    created = 0
    for fact in facts.iterator():
        created += int(TbEntregaEventoConquista.objects.get_or_create(
            evento=fact, consumidor=PURCHASE_CONSUMER)[1])
    return created


def enqueue_level_event(evento):
    if evento.origem != 'site' or evento.tipo not in (
            'character_level_up', 'character_level_reverted'):
        return None
    entrega, _ = TbEntregaEventoConquista.objects.get_or_create(
        evento=evento, consumidor=LEVEL_CONSUMER)
    return entrega


def enqueue_existing_level_events(*, user_id=None):
    facts = TbEventoConquista.objects.filter(
        origem='site', tipo__in=('character_level_up', 'character_level_reverted'))
    if user_id is not None:
        facts = facts.filter(conta_id=user_id)
    created = 0
    for fact in facts.iterator():
        created += int(TbEntregaEventoConquista.objects.get_or_create(
            evento=fact, consumidor=LEVEL_CONSUMER)[1])
    return created


def enqueue_story_event(evento):
    if evento.origem != 'site' or evento.tipo != 'story_published':
        return None
    entrega, _ = TbEntregaEventoConquista.objects.get_or_create(
        evento=evento, consumidor=STORY_CONSUMER)
    return entrega


def enqueue_existing_story_events(*, user_id=None):
    facts = TbEventoConquista.objects.filter(origem='site', tipo='story_published')
    if user_id is not None:
        facts = facts.filter(conta_id=user_id)
    created = 0
    for fact in facts.iterator():
        created += int(TbEntregaEventoConquista.objects.get_or_create(
            evento=fact, consumidor=STORY_CONSUMER)[1])
    return created


def enqueue_adventure_event(evento):
    if evento.origem != 'site_ledger' or evento.tipo not in (
            'adventure_recorded', 'adventure_reverted'):
        return None
    entrega, _ = TbEntregaEventoConquista.objects.get_or_create(
        evento=evento, consumidor=ADVENTURE_CONSUMER)
    return entrega


def enqueue_existing_adventure_events(*, user_id=None):
    facts = TbEventoConquista.objects.filter(
        origem='site_ledger', tipo__in=('adventure_recorded', 'adventure_reverted'))
    if user_id is not None:
        facts = facts.filter(conta_id=user_id)
    created = 0
    for fact in facts.iterator():
        created += int(TbEntregaEventoConquista.objects.get_or_create(
            evento=fact, consumidor=ADVENTURE_CONSUMER)[1])
    return created


def enqueue_creation_event(evento):
    if evento.origem != 'site' or evento.tipo != 'character_created':
        return None
    entrega, _ = TbEntregaEventoConquista.objects.get_or_create(
        evento=evento, consumidor=CREATION_CONSUMER)
    return entrega


def enqueue_existing_creation_events(*, user_id=None):
    facts = TbEventoConquista.objects.filter(origem='site', tipo='character_created')
    if user_id is not None:
        facts = facts.filter(conta_id=user_id)
    created = 0
    for fact in facts.iterator():
        _, new = TbEntregaEventoConquista.objects.get_or_create(
            evento=fact, consumidor=CREATION_CONSUMER)
        created += int(new)
    return created


@transaction.atomic
def reserve_creation_delivery(*, user_id=None, lease_seconds=120):
    return _reserve_delivery(CREATION_CONSUMER, user_id=user_id,
                             lease_seconds=lease_seconds)


@transaction.atomic
def reserve_adventure_delivery(*, user_id=None, lease_seconds=120):
    return _reserve_delivery(ADVENTURE_CONSUMER, user_id=user_id,
                             lease_seconds=lease_seconds)


@transaction.atomic
def reserve_story_delivery(*, user_id=None, lease_seconds=120):
    return _reserve_delivery(STORY_CONSUMER, user_id=user_id,
                             lease_seconds=lease_seconds)


@transaction.atomic
def reserve_level_delivery(*, user_id=None, lease_seconds=120):
    return _reserve_delivery(LEVEL_CONSUMER, user_id=user_id,
                             lease_seconds=lease_seconds)


@transaction.atomic
def reserve_purchase_delivery(*, user_id=None, lease_seconds=120):
    return _reserve_delivery(PURCHASE_CONSUMER, user_id=user_id,
                             lease_seconds=lease_seconds)


@transaction.atomic
def reserve_selected_delivery(delivery_id, consumer, *, lease_seconds=120):
    """Reserva somente a entrega solicitada, sem capturar outra da mesma conta."""
    return _reserve_delivery(consumer, lease_seconds=lease_seconds,
                             delivery_id=delivery_id)


def _reserve_delivery(consumer, *, user_id=None, lease_seconds=120,
                      delivery_id=None):
    now = timezone.now()
    available = (Q(estado='pendente', proxima_tentativa_em__lte=now) |
                 Q(estado='processando', reserva_ate__lte=now))
    qs = TbEntregaEventoConquista.objects.select_for_update(skip_locked=True).filter(
        consumidor=consumer).filter(available)
    if delivery_id is not None:
        qs = qs.filter(pk=delivery_id)
    if user_id is not None:
        qs = qs.filter(evento__conta_id=user_id)
    entrega = qs.order_by('criada_em', 'pk').first()
    if entrega is None:
        return None
    entrega.estado = 'processando'
    entrega.tentativas += 1
    entrega.reserva_token = uuid4()
    entrega.reserva_ate = now + timedelta(seconds=lease_seconds)
    entrega.save(update_fields=['estado', 'tentativas', 'reserva_token',
                                'reserva_ate', 'atualizada_em'])
    return entrega.pk, entrega.reserva_token


def process_creation_delivery(delivery_id, token, *, max_attempts=5):
    return _process_delivery(delivery_id, token, CREATION_CONSUMER,
                             max_attempts=max_attempts)


def process_adventure_delivery(delivery_id, token, *, max_attempts=5):
    return _process_delivery(delivery_id, token, ADVENTURE_CONSUMER,
                             max_attempts=max_attempts)


def process_story_delivery(delivery_id, token, *, max_attempts=5):
    return _process_delivery(delivery_id, token, STORY_CONSUMER,
                             max_attempts=max_attempts)


def process_level_delivery(delivery_id, token, *, max_attempts=5):
    return _process_delivery(delivery_id, token, LEVEL_CONSUMER,
                             max_attempts=max_attempts)


def process_purchase_delivery(delivery_id, token, *, max_attempts=5):
    return _process_delivery(delivery_id, token, PURCHASE_CONSUMER,
                             max_attempts=max_attempts)


def _process_delivery(delivery_id, token, consumer, *, max_attempts=5):
    """Confirma efeito e entrega juntos; reserva expirada pode ser retomada."""
    try:
        with transaction.atomic():
            entrega = (TbEntregaEventoConquista.objects.select_for_update()
                       .select_related('evento').get(pk=delivery_id))
            if (entrega.consumidor != consumer or entrega.estado != 'processando' or
                    entrega.reserva_token != token):
                return False
            if entrega.reserva_ate is None or entrega.reserva_ate <= timezone.now():
                return False
            evento = entrega.evento
            get_user_model().objects.select_for_update().only('pk').get(pk=evento.conta_id)
            if consumer == CREATION_CONSUMER:
                avaliar_inicio_classe_evento(evento)
                avaliar_primeira_ficha_evento(evento)
            elif consumer == ADVENTURE_CONSUMER:
                user = evento.conta
                avaliar_aventuras_jogadas(user)
                avaliar_quests_categorizadas(user)
            elif consumer == STORY_CONSUMER:
                avaliar_primeira_cronica_evento(evento)
            elif consumer == LEVEL_CONSUMER:
                avaliar_nivel_personagem(evento.conta)
            elif consumer == PURCHASE_CONSUMER:
                _avaliar_primeira_compra(evento.conta)
                _avaliar_unidades_compradas(evento.conta)
            else:
                raise ValueError('Consumidor de entrega desconhecido.')
            entrega.estado = 'concluida'
            entrega.reserva_token = None
            entrega.reserva_ate = None
            entrega.save(update_fields=['estado', 'reserva_token', 'reserva_ate',
                                        'atualizada_em'])
            return True
    except Exception as exc:
        with transaction.atomic():
            entrega = TbEntregaEventoConquista.objects.select_for_update().get(pk=delivery_id)
            if (entrega.consumidor == consumer and entrega.estado == 'processando' and
                    entrega.reserva_token == token):
                entrega.estado = 'revisao' if entrega.tentativas >= max_attempts else 'pendente'
                entrega.proxima_tentativa_em = timezone.now() + timedelta(
                    seconds=min(3600, 2 ** min(entrega.tentativas, 12)))
                entrega.reserva_token = None
                entrega.reserva_ate = None
                entrega.ultimo_erro = type(exc).__name__[:500]
                entrega.save(update_fields=['estado', 'proxima_tentativa_em',
                                            'reserva_token', 'reserva_ate', 'ultimo_erro',
                                            'atualizada_em'])
        return False
