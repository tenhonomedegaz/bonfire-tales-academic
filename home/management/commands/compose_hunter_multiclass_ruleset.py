"""Complete the published Hunter ruleset for existing multiclass characters."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.content_versions import create_revision, seal_ruleset
from home.models import TbClasse, TbRuleset
from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class


class Command(BaseCommand):
    help = ('Add snapshots for other classes to a sealed Hunter ruleset. '
            'Dry-run by default; never binds or converts characters.')

    def add_arguments(self, parser):
        parser.add_argument('--base-checksum', required=True)
        parser.add_argument('--expected-checksum', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                base = TbRuleset.objects.get(checksum=options['base_checksum'])
                if (base.evaluator_version, base.vocabulary_version) != (EVALUATOR, VOCABULARY):
                    raise ValueError('Unsupported Hunter ruleset semantics.')
                hunter = TbClasse.objects.get(slug='cacador')
                revisions = {entry.identity: entry.revision for entry in
                             base.entries.select_related('revision')}
                if ('hunter-rework' not in revisions or
                        f'class-catalog:{hunter.pk}' not in revisions):
                    raise ValueError('Base ruleset lacks Hunter content.')
                added = []
                for class_id in TbClasse.objects.order_by('pk').values_list('pk', flat=True):
                    identity = f'class-catalog:{class_id}'
                    if identity in revisions:
                        continue
                    revisions[identity] = create_revision(identity, inventory_class(class_id))
                    added.append(identity)
                result = seal_ruleset(revisions.values(), evaluator_version=EVALUATOR,
                                      vocabulary_version=VOCABULARY)
                if result.checksum != options['expected_checksum']:
                    raise ValueError('Class snapshots differ from the reviewed release; no changes applied.')
                output = {'checksum': result.checksum, 'ruleset_id': result.pk if options['apply'] else None,
                          'entries': len(revisions), 'class_snapshots_added': added,
                          'persisted': options['apply'], 'characters_converted': 0}
                if not options['apply']:
                    transaction.set_rollback(True)
        except (TbRuleset.DoesNotExist, TbClasse.DoesNotExist, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(output, ensure_ascii=False, sort_keys=True))
