"""Private read-only projection of existing collaborator records in the bot DB."""

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import BotMember, BotTransaction


def subscription_status(user):
    result = {'active': False, 'available': True, 'tier': '', 'expires': None,
              'history': []}
    if not getattr(user, 'is_authenticated', False) or not user.is_active:
        return result
    try:
        with transaction.atomic():
            profile = getattr(user, 'profile', None)
            emails = set()
            if profile and profile.email_verified and user.email:
                emails.add(user.email.strip())
            if profile and profile.discord_user_id:
                emails.update(email for email in BotMember.objects.filter(
                    discordUserId=profile.discord_user_id).values_list('email', flat=True)
                    if email)
            if not emails:
                return result
            identity = Q()
            for email in emails:
                identity |= Q(email__iexact=email)
            rows = BotTransaction.objects.filter(
                identity, subscriptionPlan__startswith='colaborador-')
            rank = {'conde': 1, 'marques': 2, 'duque': 3}

            def tier(record):
                parts = str(record['subscriptionPlan']).split('-')
                return parts[1] if len(parts) > 1 and parts[1] in rank else ''

            current = [record for record in rows.filter(
                status=1, expirationDate__gt=timezone.now()).values(
                    'subscriptionPlan', 'expirationDate') if tier(record)]
            if current:
                selected = max(current, key=lambda record: (
                    rank[tier(record)], record['expirationDate']))
                result.update(active=True, tier=tier(selected),
                              expires=selected['expirationDate'])
            result['history'] = list(rows.order_by('-paymentDate').values(
                'subscriptionPlan', 'paymentDate', 'expirationDate',
                'status', 'grossAmount')[:12])
    except DatabaseError:
        return {**result, 'available': False, 'active': False, 'history': []}
    return result
