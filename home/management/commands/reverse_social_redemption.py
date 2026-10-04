"""Explicit administrative compensation of a social-credit redemption."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from home.models import SocialCreditRedemption
from home.social_credits import reverse_social_redemption


class Command(BaseCommand):
    help = 'Reverse a safe redemption or record a case for administrative review.'

    def add_arguments(self, parser):
        parser.add_argument('--redemption-id', type=int, required=True)
        parser.add_argument('--actor', required=True, metavar='USERNAME')
        parser.add_argument('--reason', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm-id', type=int)

    def handle(self, *args, **options):
        redemption_id = options['redemption_id']
        if not options['apply'] or options['confirm_id'] != redemption_id:
            raise CommandError('Use --apply and --confirm-id matching --redemption-id.')
        if not SocialCreditRedemption.objects.filter(pk=redemption_id).exists():
            raise CommandError('Redemption not found.')
        actor = get_user_model().objects.filter(username=options['actor']).first()
        if actor is None or not actor.is_active or not actor.is_superuser:
            raise CommandError('An active superuser actor is required.')
        try:
            redemption, status = reverse_social_redemption(
                redemption_id, actor_id=actor.pk, reason=options['reason'])
        except (ValueError, PermissionError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Redemption {redemption.pk}: {status}.')
