"""Snapshot imported legacy rewards before their approved G01-D retirement."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from home.management.commands._redesign_dev_guard import require_redesign_dev_database
from home.management.commands.preview_redesign_d import database_identity
from home.models import TbRecompensaMestre


class Command(BaseCommand):
    help = 'Capture imported subscription rewards in isolated DEV; never snapshot the D pilot.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        require_redesign_dev_database()
        output = Path(options['output'])
        if not output.is_absolute() or output.suffix.lower() != '.json':
            raise CommandError('Use an absolute .json output path.')
        output = output.resolve()
        repo = Path(__file__).resolve().parents[3]
        if output.is_relative_to(repo) or not output.parent.is_dir() or output.exists():
            raise CommandError('Use a new snapshot path outside the repository.')

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            rows = list(TbRecompensaMestre.objects.filter(tipo='assinatura')
                        .order_by('pk').values())
            payload = {
                'kind': 'G01-D-rewards-prechange',
                'scope': 'imported_rewards_pre_retirement_only',
                'created_at': timezone.now(),
                'database_identity': database_identity(),
                'rows': {'subscription_rewards': rows},
            }
        raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          cls=DjangoJSONEncoder) + '\n').encode('utf-8')
        try:
            with output.open('xb') as stream:
                stream.write(raw)
        except FileExistsError as exc:
            raise CommandError('Output file already exists.') from exc
        self.stdout.write(json.dumps({
            'output': str(output), 'sha256': hashlib.sha256(raw).hexdigest(),
            'subscription_reward_count': len(rows),
        }, ensure_ascii=False))
