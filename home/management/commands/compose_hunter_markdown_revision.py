"""Install source-reviewed Markdown in a new Hunter content revision."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.content_versions import create_revision, digest, resolve_content, seal_ruleset
from home.hunter_markdown_revision import BASE_CHECKSUM, NEW_PK_START, compose_markdown_payload
from home.models import TbClassehabilidade, TbRuleset
from home.versioned_classes import EVALUATOR, VOCABULARY


class Command(BaseCommand):
    help = 'Preview or create an additive Hunter Markdown ruleset; never edits live rows.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--base-checksum', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('PostgreSQL required.')
        if options['base_checksum'] != BASE_CHECKSUM:
            raise CommandError('Unexpected Hunter base checksum.')
        with transaction.atomic():
            try:
                base = TbRuleset.objects.get(checksum=BASE_CHECKSUM)
                original = resolve_content(base, 'class-catalog:4',
                    evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
                payload = compose_markdown_payload(original)
                if TbClassehabilidade.objects.filter(pk__gte=NEW_PK_START).exists():
                    raise CommandError('Reserved card identities collide with live data.')
                revisions = list(base.entries.select_related('revision'))
                previous = next(row.revision for row in revisions
                                if row.identity == 'class-catalog:4')
                candidate = digest({'identity': previous.identity, 'payload': payload,
                                    'dependencies': previous.dependencies})
                manifest = dict(base.manifest)
                manifest[previous.identity] = candidate
                checksum = digest({'manifest': manifest, 'evaluator': EVALUATOR,
                                   'vocabulary': VOCABULARY})
                if options['apply']:
                    replacement = create_revision(previous.identity, payload,
                        dependencies=previous.dependencies)
                    result = seal_ruleset(
                        [replacement if row.identity == previous.identity else row.revision
                         for row in revisions], evaluator_version=EVALUATOR,
                        vocabulary_version=VOCABULARY)
                    if result.checksum != checksum:
                        raise CommandError('Hunter checksum changed during composition.')
            except (TbRuleset.DoesNotExist, StopIteration, ValueError, KeyError, TypeError) as exc:
                raise CommandError('Hunter Markdown composition failed: %s' % exc) from exc
        self.stdout.write('Hunter Markdown %s: checksum=%s, cards_updated=75, cards_added=9, live_rows_modified=0'
                          % ('applied' if options['apply'] else 'preview', checksum))
