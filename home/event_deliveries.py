"""Entrega local recuperável de fatos de criação para conquistas."""

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .conquistas import avaliar_inicio_classe_evento, avaliar_primeira_ficha_evento
from .models import TbEntregaEventoConquista, TbEventoConquista


CREATION_CONSUMER = 'conquistas_criacao_v1'


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
    now = timezone.now()
    available = (Q(estado='pendente', proxima_tentativa_em__lte=now) |
                 Q(estado='processando', reserva_ate__lte=now))
    qs = TbEntregaEventoConquista.objects.select_for_update(skip_locked=True).filter(
        consumidor=CREATION_CONSUMER).filter(available)
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
    """Confirma efeito e entrega juntos; reserva expirada pode ser retomada."""
    try:
        with transaction.atomic():
            entrega = (TbEntregaEventoConquista.objects.select_for_update()
                       .select_related('evento').get(pk=delivery_id))
            if entrega.estado != 'processando' or entrega.reserva_token != token:
                return False
            if entrega.reserva_ate is None or entrega.reserva_ate <= timezone.now():
                return False
            evento = entrega.evento
            get_user_model().objects.select_for_update().only('pk').get(pk=evento.conta_id)
            avaliar_inicio_classe_evento(evento)
            avaliar_primeira_ficha_evento(evento)
            entrega.estado = 'concluida'
            entrega.reserva_token = None
            entrega.reserva_ate = None
            entrega.save(update_fields=['estado', 'reserva_token', 'reserva_ate',
                                        'atualizada_em'])
            return True
    except Exception as exc:
        with transaction.atomic():
            entrega = TbEntregaEventoConquista.objects.select_for_update().get(pk=delivery_id)
            if entrega.estado == 'processando' and entrega.reserva_token == token:
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
