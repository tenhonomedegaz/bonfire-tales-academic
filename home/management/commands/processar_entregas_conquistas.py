"""Consulta e processa as entregas locais de conquistas em um lote limitado."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from home.event_deliveries import (
    ADVENTURE_CONSUMER, CREATION_CONSUMER, LEVEL_CONSUMER, PURCHASE_CONSUMER,
    STORY_CONSUMER,
    process_adventure_delivery, process_creation_delivery, process_level_delivery,
    process_purchase_delivery, process_story_delivery, reserve_adventure_delivery,
    reserve_creation_delivery, reserve_level_delivery, reserve_purchase_delivery,
    reserve_story_delivery,
)
from home.models import TbEntregaEventoConquista, TbEventoConquista


CONSUMERS = (
    ('criacao', CREATION_CONSUMER, 'site', ('character_created',),
     reserve_creation_delivery, process_creation_delivery),
    ('aventura', ADVENTURE_CONSUMER, 'site_ledger',
     ('adventure_recorded', 'adventure_reverted'),
     reserve_adventure_delivery, process_adventure_delivery),
    ('cronica', STORY_CONSUMER, 'site', ('story_published',),
     reserve_story_delivery, process_story_delivery),
    ('nivel', LEVEL_CONSUMER, 'site',
     ('character_level_up', 'character_level_reverted'),
     reserve_level_delivery, process_level_delivery),
    ('compra', PURCHASE_CONSUMER, 'site_market',
     ('item_purchased', 'item_purchase_refunded'),
     reserve_purchase_delivery, process_purchase_delivery),
)


class Command(BaseCommand):
    help = 'Previa por padrao; --apply reprocessa ate --limit entregas locais.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        user_id = options['user_id']
        limit = options['limit']
        if limit < 1:
            raise CommandError('O limite deve ser positivo.')
        if user_id is not None and user_id < 1:
            raise CommandError('A conta deve ter ID positivo.')

        if not options['apply']:
            now = timezone.now()
            for name, consumer, origin, types, _, _ in CONSUMERS:
                facts = TbEventoConquista.objects.filter(origem=origin, tipo__in=types)
                if user_id is not None:
                    facts = facts.filter(conta_id=user_id)
                deliveries = TbEntregaEventoConquista.objects.filter(
                    consumidor=consumer, evento__in=facts)
                available = deliveries.filter(
                    Q(estado='pendente', proxima_tentativa_em__lte=now) |
                    Q(estado='processando', reserva_ate__lte=now))
                oldest = (deliveries.exclude(estado='concluida')
                          .order_by('criada_em').values_list('criada_em', flat=True)
                          .first())
                oldest_seconds = int((now - oldest).total_seconds()) if oldest else 0
                self.stdout.write(
                    f'{name}: fatos={facts.count()} entregas={deliveries.count()} '
                    f'disponiveis={available.count()} '
                    f'revisao={deliveries.filter(estado="revisao").count()} '
                    f'com_erro={deliveries.exclude(ultimo_erro="").count()} '
                    f'idade_mais_antiga_s={oldest_seconds}')
            return

        done = failed = 0
        while done + failed < limit:
            reserved = False
            for _, _, _, _, reserve, process in CONSUMERS:
                if done + failed >= limit:
                    break
                reservation = reserve(user_id=user_id)
                if reservation is None:
                    continue
                reserved = True
                if process(*reservation):
                    done += 1
                else:
                    failed += 1
            if not reserved:
                break
        self.stdout.write(
            f'aplicado: concluidas={done} falhas={failed}')
