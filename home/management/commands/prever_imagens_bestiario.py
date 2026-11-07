"""Read-only image candidate preview; never downloads art or changes creatures."""

import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError

from home.bestiary_image_preview import SOURCE_FOLDERS, preview_images


class Command(BaseCommand):
    help = 'Gera prévia de imagens por nome original e fonte, sem baixar nem publicar arte.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='ref/Livros/Bestiary_selecao.csv')
        parser.add_argument('--fixture', default='home/fixtures/conteudo.json')
        parser.add_argument('--output', required=True)
        parser.add_argument('--repo', default='5etools-mirror-3/5etools-img')

    def handle(self, *args, **options):
        source = Path(options['csv']).resolve()
        fixture = Path(options['fixture']).resolve()
        target = Path(options['output']).resolve()
        if target in (source, fixture) or target.exists():
            raise CommandError('Saída deve ser um arquivo novo e separado das entradas.')
        repo = options['repo']
        if '/' not in repo or any(not part.replace('-', '').replace('_', '').isalnum()
                                  for part in repo.split('/')) or len(repo.split('/')) != 2:
            raise CommandError('Repositório GitHub inválido.')
        try:
            source_bytes = source.read_bytes()
            fixture_bytes = fixture.read_bytes()
            source_rows = list(csv.DictReader(StringIO(source_bytes.decode('utf-8-sig'), newline='')))
            fixture_rows = json.loads(fixture_bytes)
            creatures = [row for row in fixture_rows if row.get('model') == 'home.tbbestiario']
            if not source_rows or not creatures:
                raise ValueError('Fonte ou bestiário vazio.')
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f'Entradas inválidas: {exc}') from exc
        assets, failures = {}, {}
        for folder in sorted(set(SOURCE_FOLDERS.values())):
            url = f'https://api.github.com/repos/{repo}/contents/bestiary/{folder}'
            request = Request(url, headers={'User-Agent': 'Bonfire-Bestiary-Preview',
                                            'Accept': 'application/vnd.github+json'})
            try:
                with urlopen(request, timeout=20) as response:
                    entries = json.load(response)
                if not isinstance(entries, list):
                    raise ValueError('Listagem inesperada.')
                assets[folder] = [item for item in entries if item.get('type') == 'file']
            except (OSError, ValueError) as exc:
                failures[folder] = str(exc)[:200]
        report = preview_images(source_rows, creatures, assets)
        report['source'] = {'csv_sha256': sha256(source_bytes).hexdigest(),
                            'fixture_sha256': sha256(fixture_bytes).hexdigest(),
                            'repository': repo, 'failed_folders': failures}
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        self.stdout.write(f"Prévia: {report['summary']}; falhas: {len(failures)}; {target}")
