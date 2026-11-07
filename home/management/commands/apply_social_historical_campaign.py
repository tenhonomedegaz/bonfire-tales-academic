"""Explicit, digest-bound historical campaign application; never scheduled."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from home.models import SocialCreditPolicy
from home.social_credit_history import apply_historical_credit_campaign


class Command(BaseCommand):
    help = 'Apply one PO-approved historical credit campaign with explicit scope.'

    def add_arguments(self, parser):
        parser.add_argument('--policy', required=True)
        parser.add_argument('--campaign-key', required=True)
        parser.add_argument('--published-from', required=True)
        parser.add_argument('--published-through', required=True)
        parser.add_argument('--reactions-through', required=True)
        parser.add_argument('--expected-sha256', required=True)
        parser.add_argument('--actor', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm-policy', required=True)
        parser.add_argument('--confirm-campaign', required=True)

    def handle(self, *args, **options):
        if (not options['apply'] or options['confirm_policy'] != options['policy']
                or options['confirm_campaign'] != options['campaign_key']):
            raise CommandError('Explicit apply and matching policy/campaign confirmations required.')
        try:
            start = date.fromisoformat(options['published_from'])
            end = date.fromisoformat(options['published_through'])
            reaction_end = date.fromisoformat(options['reactions_through'])
            actor = get_user_model().objects.get(username=options['actor'])
            campaign, credits, created = apply_historical_credit_campaign(
                key=options['campaign_key'], policy_version=options['policy'],
                published_from=start, published_through=end,
                reactions_through=reaction_end,
                expected_sha256=options['expected_sha256'], actor_id=actor.pk,
            )
        except (ValueError, PermissionError, get_user_model().DoesNotExist,
                SocialCreditPolicy.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({
            'campaign_key': campaign.key,
            'status': 'applied' if created else 'already_applied',
            'credits_posted': credits, 'snapshot_sha256': campaign.snapshot_sha256,
        }))
