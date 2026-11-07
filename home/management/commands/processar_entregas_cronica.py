"""Retoma a concessão da primeira crônica a partir de fatos publicados."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from home.event_deliveries import (STORY_CONSUMER, enqueue_existing_story_events,
                                   process_story_delivery, reserve_story_delivery)
from home.models import TbEntregaEventoConquista, TbEventoConquista


class Command(BaseCommand):
    help = 'Prévia por padrão; --apply registra entregas e processa fatos de crônicas.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--resume-review-id', type=int)

    def handle(self, *args, **options):
        user_id = options['user_id']
        if options['limit'] < 1:
            raise CommandError('O limite deve ser positivo.')
        review_id = options['resume_review_id']
        if review_id is not None:
            with transaction.atomic():
                delivery = (TbEntregaEventoConquista.objects.select_for_update()
                            .filter(pk=review_id, consumidor=STORY_CONSUMER)
                            .select_related('evento').first())
                if delivery is None or delivery.estado != 'revisao':
                    raise CommandError('Entrega não encontrada em revisão.')
                if user_id is not None and user_id != delivery.evento.conta_id:
                    raise CommandError('A entrega pertence a outra conta.')
                user_id = delivery.evento.conta_id
                if options['apply']:
                    delivery.estado = 'pendente'
                    delivery.proxima_tentativa_em = timezone.now()
                    delivery.save(update_fields=['estado', 'proxima_tentativa_em',
                                                 'atualizada_em'])
                else:
                    self.stdout.write('prévia: entrega=%s estado=revisao tentativas=%s' % (
                        delivery.pk, delivery.tentativas))
                    return
        if not options['apply']:
            facts = TbEventoConquista.objects.filter(origem='site', tipo='story_published')
            if user_id is not None:
                facts = facts.filter(conta_id=user_id)
            deliveries = TbEntregaEventoConquista.objects.filter(
                consumidor=STORY_CONSUMER, evento__in=facts)
            self.stdout.write('prévia: fatos=%s entregas=%s revisao=%s' % (
                facts.count(), deliveries.count(),
                deliveries.filter(estado='revisao').count()))
            return
        created = enqueue_existing_story_events(user_id=user_id)
        done = failed = 0
        for _ in range(options['limit']):
            reservation = reserve_story_delivery(user_id=user_id)
            if reservation is None:
                break
            if process_story_delivery(*reservation):
                done += 1
            else:
                failed += 1
        self.stdout.write('aplicado: pendencias_novas=%s concluidas=%s falhas=%s' % (
            created, done, failed))
