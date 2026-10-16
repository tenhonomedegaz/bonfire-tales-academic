"""Stage reviewed local bestiary artwork; never changes catalog or publishes files."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from home.bestiary_image_stage import ImageStageError, stage_images


class Command(BaseCommand):
    help = 'Prepara arte revisada de blobs locais com checksum e miniatura, sem alterar o banco.'

    def add_arguments(self, parser):
        parser.add_argument('--preview', required=True)
        parser.add_argument('--selection', required=True)
        parser.add_argument('--blobs', required=True)
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--report', required=True)

    def handle(self, *args, **options):
        preview_path = Path(options['preview']).resolve()
        selection_path = Path(options['selection']).resolve()
        blobs_dir = Path(options['blobs']).resolve()
        output_dir = Path(options['output_dir']).resolve()
        report_path = Path(options['report']).resolve()
        if report_path.exists() or report_path in (preview_path, selection_path):
            raise CommandError('Relatório deve ser um arquivo novo e separado das entradas.')
        if not blobs_dir.is_dir():
            raise CommandError('Diretório de blobs inexistente.')
        try:
            preview_bytes = preview_path.read_bytes()
            preview = json.loads(preview_bytes)
            selection = json.loads(selection_path.read_bytes())
            if selection.get('preview_sha256') != hashlib.sha256(preview_bytes).hexdigest():
                raise ImageStageError('Hash da prévia mudou; revise a seleção.')
            def fetch_blob(sha):
                candidate = blobs_dir / sha
                if not candidate.is_file():
                    raise ImageStageError(f'Blob local ausente: {sha}')
                return candidate.read_bytes()
            staged = stage_images(preview, selection, output_dir, fetch_blob)
        except (OSError, ValueError, TypeError, KeyError, ImageStageError) as exc:
            raise CommandError(f'Preparação interrompida: {exc}') from exc
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open('x', encoding='utf-8') as handle:
            json.dump({'preview_sha256': selection['preview_sha256'], 'staged': staged},
                      handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        self.stdout.write(f'{len(staged)} imagens preparadas em {output_dir}; relatório: {report_path}')
