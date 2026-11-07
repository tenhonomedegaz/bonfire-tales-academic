"""Explicitly settle approved reader milestones; no implicit activation."""

from django.core.management.base import BaseCommand, CommandError

from home.models import SocialCreditPolicy, SocialCreditReaderRecognition
from home.social_credits import settle_reader_milestones


class Command(BaseCommand):
    help = 'Apply due reader milestones only for an active policy explicitly confirmed by version.'

    def add_arguments(self, parser):
        parser.add_argument('--policy', required=True, metavar='VERSION')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm-version', metavar='VERSION')

    def handle(self, *args, **options):
        if not options['apply'] or options['confirm_version'] != options['policy']:
            raise CommandError('Use --apply and --confirm-version with the same policy version.')
        policy = SocialCreditPolicy.objects.filter(version=options['policy'], active=True).first()
        if policy is None:
            raise CommandError('No active policy with that version.')
        story_ids = list(SocialCreditReaderRecognition.objects.filter(
            policy=policy).order_by().values_list('cronica_id', flat=True).distinct())
        entry_count = 0
        credit_count = 0
        for story_id in sorted(story_ids):
            try:
                entries = settle_reader_milestones(policy.pk, story_id)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            entry_count += len(entries)
            credit_count += sum(entry.delta for entry in entries)
        self.stdout.write(self.style.SUCCESS(
            f'{entry_count} reader milestone(s) posted; {credit_count} credit(s) granted.'
        ))
