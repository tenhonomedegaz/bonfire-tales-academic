"""Preview and explicitly apply separately approved historical credit campaigns."""

import hashlib
import json
import re
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Sum
from django.utils import timezone

from .models import (SocialCreditEntry, SocialCreditHistoricalCampaign,
                     SocialCreditReaderRecognition, SocialCreditPolicy, TbCronica,
                     TbCronicaCurtida)
from .social_credits import _validate_reader_policy, post_social_credit


def preview_historical_credit_campaign(policy, *, published_from, published_through,
                                       reactions_through, as_of=None):
    """Estimate old-story awards without creating a wallet, entry or recognition.

    Only reactions preserved without a policy and still present before the campaign
    cutoff qualify. The report is not authorization to post historical credits.
    """
    now = as_of or timezone.now()
    if (type(published_from) is not date or type(published_through) is not date
            or type(reactions_through) is not date
            or published_from > published_through
            or published_through > reactions_through or reactions_through > now.date()):
        raise ValueError('invalid historical publication or reaction date range')
    if type(policy.first_publication_amount) is not int or policy.first_publication_amount <= 0:
        raise ValueError('first publication amount must be positive')
    if policy.reader_recognition_enabled:
        _validate_reader_policy(policy)

    stories = TbCronica.objects.filter(
        status='aprovada', data_publicacao__date__gte=published_from,
        data_publicacao__date__lte=published_through,
        autor__is_active=True,
    ).order_by('data_publicacao', 'pk').values('pk', 'autor_id')
    author_spent = {}
    rows = []
    for story in stories:
        story_id, author_id = story['pk'], story['autor_id']
        first_ref = f'chronicle:{story_id}:first_publication'
        first_awarded = SocialCreditEntry.objects.filter(operation_ref=first_ref).exists()
        first_credits = 0 if first_awarded else policy.first_publication_amount
        readers = milestones = reader_credits = 0
        prior_reader_award = False
        if policy.reader_recognition_enabled:
            current_like = TbCronicaCurtida.objects.filter(
                cronica_id=OuterRef('cronica_id'), leitor_id=OuterRef('reader_id'),
                criado_em__date__lte=reactions_through,
            )
            readers = (SocialCreditReaderRecognition.objects.filter(
                cronica_id=story_id, policy__isnull=True,
                first_seen_at__date__lte=reactions_through,
                first_seen_at__lte=now - timedelta(hours=policy.reader_consolidation_hours),
                reader__is_active=True,
            ).exclude(reader_id=F('cronica__autor_id'))
                .annotate(current_like=Exists(current_like))
                .filter(current_like=True).count())
            previous = SocialCreditEntry.objects.filter(
                wallet__user_id=author_id,
                kind__in=('reader_milestone', 'historical_reader_milestone'),
                operation_ref__startswith=f'chronicle:{story_id}:',
            )
            prior_reader_award = previous.exists()
            if not prior_reader_award:
                if author_id not in author_spent:
                    author_spent[author_id] = (SocialCreditEntry.objects.filter(
                        wallet__user_id=author_id,
                        kind__in=('reader_milestone', 'historical_reader_milestone'),
                        created_at__gte=now - timedelta(days=policy.reader_period_days),
                        created_at__lte=now,
                    ).aggregate(total=Sum('delta'))['total'] or 0)
                amount = policy.reader_milestone_amount
                milestones = min(
                    readers // policy.reader_milestone_size,
                    policy.reader_story_credit_cap // amount,
                    max(0, policy.reader_author_period_credit_cap - author_spent[author_id]) // amount,
                )
                reader_credits = milestones * amount
                author_spent[author_id] += reader_credits
        rows.append({
            'chronicle_id': story_id, 'author_id': author_id,
            'first_publication_credits': first_credits,
            'historical_readers': readers,
            'reader_award_already_exists': prior_reader_award,
            'reader_milestones': milestones,
            'reader_credits': reader_credits,
            'total_credits': first_credits + reader_credits,
        })
    return rows


def historical_campaign_digest(policy, published_from, published_through,
                               reactions_through, rows):
    """Bind explicit approval to rule values, cutoffs and projected recipients."""
    fields = ('first_publication_amount', 'reader_recognition_enabled',
              'reader_milestone_size', 'reader_milestone_amount',
              'reader_consolidation_hours', 'reader_story_credit_cap',
              'reader_author_period_credit_cap', 'reader_period_days')
    payload = {
        'policy': policy.version,
        'rules': {name: getattr(policy, name) for name in fields},
        'published_from': published_from.isoformat(),
        'published_through': published_through.isoformat(),
        'reactions_through': reactions_through.isoformat(),
        'rows': rows,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


@transaction.atomic
def apply_historical_credit_campaign(*, key, policy_version, published_from,
                                     published_through, reactions_through,
                                     expected_sha256, actor_id):
    """Apply a confirmed snapshot exactly once; never infer commercial approval."""
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,39}', key or ''):
        raise ValueError('invalid campaign key')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256 or ''):
        raise ValueError('invalid expected snapshot digest')
    actor = get_user_model().objects.get(pk=actor_id)
    if not actor.is_active or not actor.is_superuser:
        raise PermissionError('campaign requires an active superuser')
    policy = SocialCreditPolicy.objects.select_for_update().get(version=policy_version)
    prior = SocialCreditHistoricalCampaign.objects.filter(key=key).first()
    if prior:
        if (prior.policy_id != policy.pk or prior.published_from != published_from
                or prior.published_through != published_through
                or prior.reactions_through != reactions_through
                or prior.snapshot_sha256 != expected_sha256):
            raise ValueError('campaign key already belongs to another approval scope')
        return prior, 0, False
    if not policy.active:
        raise ValueError('historical campaign policy is inactive')
    # Serialize selected stories against moderation and existing reactions.
    story_ids = list(TbCronica.objects.select_for_update().filter(
        status='aprovada', data_publicacao__date__gte=published_from,
        data_publicacao__date__lte=published_through,
    ).order_by('pk').values_list('pk', flat=True))
    list(TbCronicaCurtida.objects.select_for_update().filter(
        cronica_id__in=story_ids,
    ).order_by('pk').values_list('pk', flat=True))
    list(SocialCreditReaderRecognition.objects.select_for_update().filter(
        cronica_id__in=story_ids,
    ).order_by('pk').values_list('pk', flat=True))
    rows = preview_historical_credit_campaign(
        policy, published_from=published_from, published_through=published_through,
        reactions_through=reactions_through,
    )
    digest = historical_campaign_digest(policy, published_from, published_through,
                                        reactions_through, rows)
    if digest != expected_sha256:
        raise ValueError('historical campaign snapshot changed; preview again')
    campaign = SocialCreditHistoricalCampaign.objects.create(
        key=key, policy=policy, published_from=published_from,
        published_through=published_through, reactions_through=reactions_through,
        snapshot_sha256=digest, applied_by=actor,
    )
    credits = 0
    for row in rows:
        story_id, author_id = row['chronicle_id'], row['author_id']
        if row['first_publication_credits']:
            _, created = post_social_credit(
                author_id, operation_ref=f'chronicle:{story_id}:first_publication',
                kind='first_publication', delta=row['first_publication_credits'],
                policy=policy,
            )
            if not created:
                raise ValueError('publication award changed during campaign')
            credits += row['first_publication_credits']
        for number in range(1, row['reader_milestones'] + 1):
            _, created = post_social_credit(
                author_id,
                operation_ref=f'chronicle:{story_id}:historical_reader_milestone:{key}:{number}',
                kind='historical_reader_milestone',
                delta=policy.reader_milestone_amount, policy=policy,
            )
            if not created:
                raise ValueError('reader award changed during campaign')
            credits += policy.reader_milestone_amount
    return campaign, credits, True
