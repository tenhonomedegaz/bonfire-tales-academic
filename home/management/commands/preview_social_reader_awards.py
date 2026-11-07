"""Read-only projection; this command never posts social credits."""

import json

from django.core.management.base import BaseCommand, CommandError

from home.models import SocialCreditPolicy
from home.social_credits import preview_reader_milestones


class Command(BaseCommand):
    help = 'Preview consolidated reader milestones for a versioned policy without granting credits.'

    def add_arguments(self, parser):
        parser.add_argument('--policy', required=True, metavar='VERSION')

    def handle(self, *args, **options):
        policy = SocialCreditPolicy.objects.filter(version=options['policy']).first()
        if policy is None:
            raise CommandError('Unknown social credit policy version.')
        try:
            rows = preview_reader_milestones(policy)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({
            'policy': policy.version, 'active': policy.active,
            'mode': 'preview_only', 'rows': rows,
        }, ensure_ascii=False))
