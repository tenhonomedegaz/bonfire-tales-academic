"""Retired scheduler entry point; cannot debit or revoke lifetime Mestre Ouro."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Legacy monthly billing is disabled; Mestre Ouro is lifetime.'

    def handle(self, *args, **options):
        self.stdout.write('Mestre Ouro vitalício: cobrança mensal desativada; 0 débitos.')
