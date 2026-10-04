"""Explicit compensation of social credits granted to a hidden Chronicle."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from home.social_credits import reverse_moderated_story_credits


class Command(BaseCommand):
    help = 'Reverse awards tied to a hidden-story report or flag insufficient balance.'

    def add_arguments(self, parser):
        parser.add_argument('--report-id', type=int, required=True)
        parser.add_argument('--actor', required=True, metavar='USERNAME')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm-id', type=int)

    def handle(self, *args, **options):
        report_id = options['report_id']
        if not options['apply'] or options['confirm_id'] != report_id:
            raise CommandError('Use --apply and --confirm-id matching --report-id.')
        actor = get_user_model().objects.filter(username=options['actor']).first()
        if actor is None or not actor.is_active or not actor.is_superuser:
            raise CommandError('An active superuser actor is required.')
        try:
            reversals, state = reverse_moderated_story_credits(
                report_id, actor_id=actor.pk,
            )
        except (ValueError, PermissionError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Report {report_id}: {state}; {len(reversals)} reversal(s).')
