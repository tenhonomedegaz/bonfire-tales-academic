from django.core.management.base import BaseCommand, CommandError

from home.ranger_reference import compare_fixture, extract_reference, write_draft


class Command(BaseCommand):
    help = 'Extract the complete ranger source draft and compare a fixture; no database writes.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True)
        parser.add_argument('--baseline', required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--inventory', action='store_true')
        parser.add_argument('--content-output')

    def handle(self, *args, **options):
        try:
            if options['inventory']:
                from home.hunter_inventory import build_inventory, content_catalog
                from pathlib import Path
                docs = [Path('docs/criador-personagem') / name for name in (
                    'dicionario-tags.md', 'vocabulario-tags-json.md',
                    'novos-verbos-pendentes.md', 'bestiario-e-summon.md')]
                inventory = build_inventory(options['source'], options['baseline'], docs)
                write_draft(options['output'], inventory)
                if options['content_output']:
                    write_draft(options['content_output'], content_catalog(inventory))
                self.stdout.write(str(inventory['coverage']))
                return
            draft = extract_reference(options['source'])
            comparison = compare_fixture(draft, options['baseline'])
            write_draft(options['output'], {'draft': draft, 'comparison': comparison})
        except (OSError, ValueError, KeyError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write('Draft: %d entries, %d orders, 20 levels; %d baseline features. No activation.' % (
            len(draft['entries']), len(draft['orders']), len(comparison['features'])))
