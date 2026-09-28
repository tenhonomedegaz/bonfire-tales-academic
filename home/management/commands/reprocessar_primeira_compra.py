"""Reprocessa somente compras com identidade e ledger válidos."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from home.conquistas import reprocessar_primeira_compra
from home.models import TbTransacao, TbUsuarioConquista


class Command(BaseCommand):
    help = 'Prévia por padrão; --apply grava fatos e reavalia conquistas de compra.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        user_ids = set(TbTransacao.objects.filter(
            tipo__in=['compra', 'mercado-compra']).values_list(
                'id_personagem__dono_id', flat=True))
        user_ids.update(TbUsuarioConquista.objects.filter(
            conquista__criterio_json__metric__in=[
                'items_purchased', 'items_purchased_units']).values_list('user_id', flat=True))
        if options['user_id'] is not None:
            user_ids &= {options['user_id']}
        total = {'novas': 0, 'invalidas': 0}
        for user in get_user_model().objects.filter(pk__in=user_ids).order_by('pk'):
            with transaction.atomic():
                result = reprocessar_primeira_compra(user)
                for key in total:
                    total[key] += result[key]
                if not options['apply']:
                    transaction.set_rollback(True)
        self.stdout.write('%s: contas=%s fatos_novos=%s invalidas=%s' % (
            'aplicado' if options['apply'] else 'prévia', len(user_ids),
            total['novas'], total['invalidas']))
