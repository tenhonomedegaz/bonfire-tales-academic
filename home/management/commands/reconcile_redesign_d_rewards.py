"""Reversible G01-D retirement of legacy subscription catalog entries.

This changes catalog visibility only. Historical rights, transactions and balances
are deliberately outside this command's write set.
"""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.models import TbRecompensaMestre
from home.management.commands.preview_redesign_d import database_identity


def _read_json(path, digest):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise CommandError('Artifact SHA-256 does not match.')
    return json.loads(raw)


class Command(BaseCommand):
    help = 'Preview, retire or restore G01-D subscription rewards using a verified prechange snapshot.'

    def add_arguments(self, parser):
        parser.add_argument('--snapshot', required=True)
        parser.add_argument('--sha256', required=True)
        parser.add_argument('--action', choices=('preview', 'retire', 'restore'), default='preview')
        parser.add_argument('--confirm', default='')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('G01-D changes require PostgreSQL.')
        if options['action'] != 'preview' and options['confirm'] != 'G01-D-REWARDS':
            raise CommandError('Write requires --confirm G01-D-REWARDS.')
        try:
            saved = _read_json(options['snapshot'], options['sha256'])
        except (OSError, ValueError) as exc:
            raise CommandError(f'Invalid snapshot: {exc}') from exc
        if saved.get('kind') != 'G01-D-prechange':
            raise CommandError('Not a G01-D prechange snapshot.')
        if saved.get('database_identity') != database_identity():
            raise CommandError('Snapshot belongs to a different database connection.')
        originals = saved.get('rows', {}).get('subscription_rewards')
        if not isinstance(originals, list):
            raise CommandError('Snapshot lacks subscription rewards.')
        by_id = {row['id_recompensa']: row for row in originals}
        if len(by_id) != len(originals) or any(row.get('tipo') != 'assinatura' for row in originals):
            raise CommandError('Snapshot subscription rewards are invalid.')

        with transaction.atomic():
            current = list(TbRecompensaMestre.objects.filter(tipo='assinatura')
                           .select_for_update().order_by('pk'))
            if {row.pk for row in current} != set(by_id):
                raise CommandError('Subscription catalog changed since snapshot.')
            changed = []
            for row in current:
                original = by_id[row.pk]
                # Compare all snapshotted fields except the one this operation owns.
                for field, value in original.items():
                    if field != 'ativo' and getattr(row, field) != value:
                        raise CommandError(f'Reward {row.pk} changed since snapshot ({field}).')
                if options['action'] == 'restore':
                    # Restore only entries originally active. Already inactive entries
                    # must remain inactive; a newly active entry is an unsafe conflict.
                    if not original['ativo'] and row.ativo:
                        raise CommandError(f'Reward {row.pk} was activated outside G01-D.')
                    target = original['ativo']
                else:
                    if row.ativo != original['ativo'] and options['action'] == 'retire':
                        raise CommandError(f'Reward {row.pk} state differs from snapshot.')
                    target = False
                if row.ativo != target:
                    changed.append(row.pk)
                    if options['action'] != 'preview':
                        row.ativo = target
                        row.save(update_fields=['ativo'])
        self.stdout.write(json.dumps({'action': options['action'], 'changed_reward_ids': changed,
                                      'count': len(changed)}, ensure_ascii=False))
