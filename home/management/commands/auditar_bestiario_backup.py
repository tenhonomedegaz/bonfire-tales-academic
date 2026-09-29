"""Produce a review queue from a JSON backup without connecting to the database."""

from hashlib import sha256
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from home.bestiary_audit import audit_snapshot


class Command(BaseCommand):
    help = 'Audita o bestiário de um backup JSON sem gravar no banco ou alterar o backup.'

    def add_arguments(self, parser):
        parser.add_argument('--backup', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        source = Path(options['backup']).resolve()
        target = Path(options['output']).resolve()
        if source == target:
            raise CommandError('O relatório deve ser separado do backup original.')
        if target.exists():
            raise CommandError('O arquivo de saída já existe; escolha outro caminho.')
        try:
            raw = source.read_bytes()
            rows = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise CommandError(f'Backup inválido: {exc}') from exc
        if not isinstance(rows, list):
            raise CommandError('Backup precisa ser uma lista de registros serializados.')
        report = audit_snapshot(rows)
        if not report['summary']['creatures']:
            raise CommandError('Nenhuma criatura encontrada no backup.')
        report['source'] = {'file': source.name, 'sha256': sha256(raw).hexdigest()}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(
            f"Auditadas {report['summary']['creatures']} criaturas; "
            f"{len(report['repair_candidates'])} candidatos de reparo; "
            f"relatório: {target}"
        )
