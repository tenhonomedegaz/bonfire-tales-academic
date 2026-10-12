"""Preview or restore canonical facts for previously completed cosmetic redemptions."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.event_cosmetics import event_cosmetic_fact_fields
from home.models import EventCosmeticRedemption, TbEventoConquista


def _fact_matches(fact, expected):
    return (fact.tipo == expected['tipo']
            and fact.versao_payload == 1
            and fact.conta_id == expected['conta_id']
            and fact.personagem_id == expected['personagem_id']
            and fact.agregado_id == expected['agregado_id']
            and fact.ocorrido_em == expected['ocorrido_em']
            and fact.payload_json == expected['payload_json'])


class Command(BaseCommand):
    help = ('Preview historical event cosmetic facts; apply only after reviewing '
            'the exact number of missing facts.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--expected-missing', type=int)

    def handle(self, *args, **options):
        apply = options['apply']
        expected_missing = options['expected_missing']
        if apply and (expected_missing is None or expected_missing < 0):
            raise CommandError('--apply requires --expected-missing from a fresh preview.')

        with transaction.atomic():
            redemptions = EventCosmeticRedemption.objects.order_by('pk')
            if apply:
                redemptions = redemptions.select_for_update()
            scanned = missing = 0
            pending = []
            for redemption in redemptions.iterator():
                scanned += 1
                fields = event_cosmetic_fact_fields(redemption)
                existing = TbEventoConquista.objects.filter(
                    origem=fields['origem'], chave_origem=fields['chave_origem']).first()
                if existing:
                    if not _fact_matches(existing, fields):
                        raise CommandError(
                            f'Conflicting event fact for redemption {redemption.pk}; no changes committed.')
                    continue
                missing += 1
                pending.append(fields)

            if apply and missing != expected_missing:
                raise CommandError(
                    f'Missing fact count changed: expected {expected_missing}, found {missing}; '
                    'no changes committed.')
            created_count = 0
            if apply:
                for fields in pending:
                    fact, created = TbEventoConquista.objects.get_or_create(
                        origem=fields['origem'], chave_origem=fields['chave_origem'],
                        defaults={key: value for key, value in fields.items()
                                  if key not in {'origem', 'chave_origem'}},
                    )
                    if not _fact_matches(fact, fields):
                        raise CommandError('Conflicting event fact appeared; no changes committed.')
                    created_count += int(created)

        self.stdout.write(json.dumps({
            'status': 'applied' if apply else 'preview',
            'redemptions_scanned': scanned,
            'facts_missing': missing,
            'facts_created': created_count,
        }))
