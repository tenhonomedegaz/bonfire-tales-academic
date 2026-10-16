"""Preview or explicitly apply prepared and reviewed bestiary thumbnails."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from home.bestiary_image_publish import ImagePublicationError, publication_plan, publish_images


class Command(BaseCommand):
    help = 'Prévia por padrão; --apply vincula miniaturas revisadas apenas a criaturas oficiais sem arte.'

    def add_arguments(self, parser):
        parser.add_argument('--report', required=True)
        parser.add_argument('--stage-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            report = json.loads(Path(options['report']).read_text(encoding='utf-8'))
            if options['apply']:
                rows = publish_images(report, options['stage_dir'])
            else:
                rows = publication_plan(report, options['stage_dir'])
        except (OSError, ValueError, TypeError, ImagePublicationError) as exc:
            raise CommandError(f'Publicação interrompida: {exc}') from exc
        self.stdout.write(json.dumps({
            'mode': 'applied' if options['apply'] else 'preview',
            'count': len(rows),
            'creatures': [{key: row[key] for key in ('pk', 'slug', 'url', 'sha256', 'already_linked')}
                          for row in rows],
        }, ensure_ascii=False))
