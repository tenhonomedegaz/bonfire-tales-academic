"""Write an isolated, identity-checked reconciliation artifact; never touch DB."""

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from django.core.management.base import BaseCommand, CommandError

from home.bestiary_repair import RepairConflict, reconcile_snapshot


class Command(BaseCommand):
    help = 'Gera cópia reconciliada do backup após validar identidades, revisão e hash.'

    def add_arguments(self, parser):
        parser.add_argument('--backup', required=True)
        parser.add_argument('--audit', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        source = Path(options['backup']).resolve()
        audit_path = Path(options['audit']).resolve()
        target = Path(options['output']).resolve()
        if len({source, audit_path, target}) != 3:
            raise CommandError('Backup, auditoria e saída devem ser arquivos distintos.')
        if target.exists():
            raise CommandError('A saída já existe; não será sobrescrita.')
        try:
            raw = source.read_bytes()
            rows = json.loads(raw)
            report = json.loads(audit_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Entrada inválida: {exc}') from exc
        if report.get('source', {}).get('sha256') != sha256(raw).hexdigest():
            raise CommandError('O hash do backup não corresponde à auditoria.')
        try:
            reconciled, counts = reconcile_snapshot(rows, report)
        except RepairConflict as exc:
            raise CommandError(f'Conflito de reconciliação: {exc}') from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                             prefix=target.name + '.', suffix='.tmp',
                                             delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(reconciled, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            # Link creation is exclusive: a concurrent file is never replaced.
            os.link(temporary, target)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        self.stdout.write(f"Cópia isolada: {target}; aplicados={counts['applied']}; "
                          f"inalterados={counts['unchanged']}; banco não acessado.")
