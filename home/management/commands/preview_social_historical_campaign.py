"""Preview old Chronicle awards. This command has no apply mode."""

import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from home.models import SocialCreditPolicy
from home.social_credit_history import (historical_campaign_digest,
                                        preview_historical_credit_campaign)


class Command(BaseCommand):
    help = 'Simulate historical Chronicle credits under a policy; never posts credits.'

    def add_arguments(self, parser):
        parser.add_argument('--policy', required=True, metavar='VERSION')
        parser.add_argument('--published-from', required=True, metavar='YYYY-MM-DD')
        parser.add_argument('--published-through', required=True, metavar='YYYY-MM-DD')
        parser.add_argument('--reactions-through', required=True, metavar='YYYY-MM-DD')

    def handle(self, *args, **options):
        policy = SocialCreditPolicy.objects.filter(version=options['policy']).first()
        if policy is None:
            raise CommandError('Unknown social credit policy version.')
        try:
            start = date.fromisoformat(options['published_from'])
            end = date.fromisoformat(options['published_through'])
            reactions_end = date.fromisoformat(options['reactions_through'])
            rows = preview_historical_credit_campaign(
                policy, published_from=start, published_through=end,
                reactions_through=reactions_end,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({
            'mode': 'preview_only', 'policy': policy.version,
            'published_from': start.isoformat(), 'published_through': end.isoformat(),
            'reactions_through': reactions_end.isoformat(),
            'rows': rows, 'total_credits': sum(row['total_credits'] for row in rows),
            'snapshot_sha256': historical_campaign_digest(
                policy, start, end, reactions_end, rows),
        }, ensure_ascii=False))
