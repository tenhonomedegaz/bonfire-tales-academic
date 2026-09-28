"""Compose the corrected Hunter multiclass basics in a new sealed ruleset."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.hunter_catalog import compose_class_basics_revision
from home.models import TbClasse, TbRuleset


class Command(BaseCommand):
    help = 'Compose reviewed Hunter class basics; dry-run by default and never converts characters.'

    def add_arguments(self, parser):
        parser.add_argument('--base-checksum', required=True)
        parser.add_argument('--expected-checksum', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                base = TbRuleset.objects.get(checksum=options['base_checksum'])
                hunter = TbClasse.objects.get(slug='cacador')
                result = compose_class_basics_revision(base, class_id=hunter.pk)
                if result.checksum != options['expected_checksum']:
                    raise ValueError('Composed checksum differs from the reviewed target.')
                output = {'checksum': result.checksum,
                          'ruleset_id': result.pk if options['apply'] else None,
                          'persisted': options['apply'], 'characters_converted': 0}
                if not options['apply']:
                    transaction.set_rollback(True)
        except (TbRuleset.DoesNotExist, TbClasse.DoesNotExist, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(output, ensure_ascii=False, sort_keys=True))
