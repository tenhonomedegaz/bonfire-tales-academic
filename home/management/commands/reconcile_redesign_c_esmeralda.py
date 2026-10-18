"""Reconcile the already approved level-13 slot in the dedicated redesign DEV DB."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.conquistas import (_marcos_rank_comprovados,
                             registrar_slot_esmeralda_comprovado)
from home.models import TbEventoConquista


class Command(BaseCommand):
    help = 'Preview or apply the proven level-13 Esmeralda slot, without MM or tokens.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm', default='')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('G01-C reconciliation requires PostgreSQL.')
        with connection.cursor() as cursor:
            cursor.execute('select current_database(), inet_server_addr()')
            database, address = cursor.fetchone()
        if options['apply'] and (
                options['confirm'] != 'G01-C-LEVEL13' or
                database != 'bonfire_redesign_6113ea68' or
                str(address) not in ('::1', '127.0.0.1')):
            raise CommandError('Write requires dedicated local DEV and --confirm G01-C-LEVEL13.')

        candidates = []
        granted = []
        with transaction.atomic():
            if not options['apply']:
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            account_ids = sorted(set(TbEventoConquista.objects.filter(
                origem='site', tipo='character_level_up',
                payload_json__level_after__gte=13,
            ).values_list('conta_id', flat=True)))
            for user in get_user_model().objects.filter(pk__in=account_ids).order_by('pk'):
                proof = next(((level, event) for level, event in
                              _marcos_rank_comprovados(user) if level >= 13), None)
                if proof is None:
                    continue
                key = f'conta:{user.pk}:slot-esmeralda-nivel-13'
                exists = TbEventoConquista.objects.filter(
                    origem='site', chave_origem=key).exists()
                candidates.append({'user_id': user.pk, 'level': proof[0],
                                   'already_recorded': exists})
                if options['apply']:
                    get_user_model().objects.select_for_update().get(pk=user.pk)
                    registrar_slot_esmeralda_comprovado(user)
                    if not exists:
                        granted.append(user.pk)
        self.stdout.write(json.dumps({
            'database': database, 'server_address': str(address),
            'applied': options['apply'], 'candidates': candidates,
            'granted_user_ids': granted,
        }, sort_keys=True))
