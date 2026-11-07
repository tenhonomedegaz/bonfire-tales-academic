"""Compensate one G01-D MM theme redemption without deleting its audit trail."""

from django.core.management.base import BaseCommand, CommandError

from home.models import CosmeticMMRedemption
from home.theme_mm import reverse_theme_mm
from home.management.commands._redesign_dev_guard import require_redesign_dev_database


class Command(BaseCommand):
    help = 'Estorna um resgate de tema em MM e preserva recibo e ledger.'

    def add_arguments(self, parser):
        parser.add_argument('redemption_id', type=int)
        parser.add_argument('--confirm', default='')

    def handle(self, *args, **options):
        if options['confirm'] != 'G01-D-MM-REVERSAL':
            raise CommandError('Informe --confirm G01-D-MM-REVERSAL para estornar.')
        require_redesign_dev_database()
        if not CosmeticMMRedemption.objects.filter(pk=options['redemption_id']).exists():
            raise CommandError('Recibo MM não encontrado.')
        try:
            receipt, changed = reverse_theme_mm(options['redemption_id'])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'receipt={receipt.pk} reversed={changed} '
                          f'compensation={receipt.reversal_transaction_id}')
