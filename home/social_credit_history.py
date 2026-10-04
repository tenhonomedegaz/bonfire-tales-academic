"""Read-only simulation for a separately approved historical credit campaign."""

from datetime import date, timedelta

from django.db.models import Exists, F, OuterRef, Sum
from django.utils import timezone

from .models import (SocialCreditEntry, SocialCreditReaderRecognition, TbCronica,
                     TbCronicaCurtida)
from .social_credits import _validate_reader_policy


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
                wallet__user_id=author_id, kind='reader_milestone',
                operation_ref__startswith=f'chronicle:{story_id}:reader_milestone:',
            )
            prior_reader_award = previous.exists()
            if not prior_reader_award:
                if author_id not in author_spent:
                    author_spent[author_id] = (SocialCreditEntry.objects.filter(
                        wallet__user_id=author_id, kind='reader_milestone',
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
