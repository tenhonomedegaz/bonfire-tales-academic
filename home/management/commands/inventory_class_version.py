"""Consistent, read-only baseline inventory for editorial review."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.content_versions import digest
from home.models import TbClasse, TbPersonagemClasse
from home.versioned_classes import inventory_class


class Command(BaseCommand):
    help = 'Inventory current class content and affected character count without database writes.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--class-slug', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('PostgreSQL is required.')
        if Path(options['output']).exists():
            raise CommandError('Output already exists; refusing to overwrite.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            classe = TbClasse.objects.get(slug=options['class_slug'])
            payload = inventory_class(classe.pk)
            payload['affected_characters'] = TbPersonagemClasse.objects.filter(
                id_classe=classe).values('id_personagem').distinct().count()
            payload['source'] = 'database-read-only-repeatable-read'
            payload['checksum'] = digest(payload)
        with Path(options['output']).open('x', encoding='utf-8') as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write('\n')
        self.stdout.write('Inventory saved; %d affected characters. No database writes.' % payload['affected_characters'])
