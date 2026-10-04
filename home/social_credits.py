"""Account credit ledger. Economic rules must be approved before callers issue credits."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Sum
from django.utils import timezone

from .models import (SocialCreditEntry, SocialCreditPolicy, SocialCreditReaderRecognition,
                     SocialCreditWallet, TbCronicaCurtida)


@transaction.atomic
def post_social_credit(user_id, *, operation_ref, kind, delta, policy=None):
    """Post once per reference, atomically preserving a nonnegative account balance."""
    if not isinstance(delta, int) or isinstance(delta, bool) or delta == 0:
        raise ValueError('delta must be a nonzero integer')
    if not isinstance(operation_ref, str) or not operation_ref or len(operation_ref) > 160:
        raise ValueError('operation_ref must be a nonempty reference of at most 160 characters')
    if not isinstance(kind, str) or not kind or len(kind) > 40:
        raise ValueError('kind must be a nonempty code of at most 40 characters')

    # Lock the account first, including when its wallet has not been created yet.
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    prior = SocialCreditEntry.objects.filter(operation_ref=operation_ref).select_related('wallet').first()
    if prior:
        if (prior.wallet.user_id != user.pk or prior.kind != kind or prior.delta != delta
                or prior.policy_id != (policy.pk if policy else None)):
            raise ValueError('operation_ref already belongs to a different posting')
        return prior, False

    wallet, _ = SocialCreditWallet.objects.get_or_create(user=user)
    new_balance = wallet.balance + delta
    if new_balance < 0:
        raise ValueError('insufficient social credit balance')
    entry = SocialCreditEntry.objects.create(
        wallet=wallet, operation_ref=operation_ref, kind=kind, delta=delta,
        balance_after=new_balance, policy=policy,
    )
    wallet.balance = new_balance
    wallet.save(update_fields=['balance', 'updated_at'])
    return entry, True


@transaction.atomic
def reverse_social_credit(entry_id, *, operation_ref):
    """Compensate an entry once, retaining both records and refusing negative balances."""
    original = SocialCreditEntry.objects.select_related('wallet').get(pk=entry_id)
    get_user_model().objects.select_for_update().get(pk=original.wallet.user_id)
    existing = SocialCreditEntry.objects.filter(reversal_of=original).first()
    if existing:
        if existing.operation_ref != operation_ref:
            raise ValueError('entry already has a different reversal')
        return existing, False
    reversal, created = post_social_credit(
        original.wallet.user_id, operation_ref=operation_ref,
        kind='compensation', delta=-original.delta,
    )
    if not created:
        raise ValueError('operation_ref already belongs to another entry')
    reversal.reversal_of = original
    reversal.save(update_fields=['reversal_of'])
    return reversal, True


def award_first_chronicle_publication(cronica):
    """Award only on a new approved publication while an explicit rule is active."""
    if cronica.status != 'aprovada' or not cronica.data_publicacao or not cronica.autor.is_active:
        return None
    reference = f'chronicle:{cronica.pk}:first_publication'
    prior = SocialCreditEntry.objects.filter(operation_ref=reference).first()
    if prior:
        return prior
    policy = SocialCreditPolicy.objects.filter(active=True).first()
    if policy is None:
        return None
    entry, _ = post_social_credit(
        cronica.autor_id, operation_ref=reference,
        kind='first_publication', delta=policy.first_publication_amount, policy=policy,
    )
    return entry


def record_reader_recognition(cronica, reader):
    """Remember a first like; inactive rules never qualify old or toggled likes."""
    if cronica.status != 'aprovada' or cronica.autor_id == reader.pk:
        return None
    policy = None
    if (reader.is_active and cronica.autor.is_active and cronica.data_publicacao):
        policy = SocialCreditPolicy.objects.filter(
            active=True, reader_recognition_enabled=True,
        ).first()
    recognition, _ = SocialCreditReaderRecognition.objects.get_or_create(
        cronica=cronica, reader=reader, defaults={'policy': policy},
    )
    return recognition


def preview_reader_milestones(policy, *, as_of=None):
    """Read-only projection of consolidated reader milestones under one policy."""
    fields = (
        'reader_milestone_size', 'reader_milestone_amount',
        'reader_consolidation_hours', 'reader_story_credit_cap',
        'reader_author_period_credit_cap', 'reader_period_days',
    )
    if not policy.reader_recognition_enabled or any(
        not isinstance(getattr(policy, field), int) or getattr(policy, field) <= 0
        for field in fields
    ):
        raise ValueError('reader recognition policy is incomplete or disabled')
    now = as_of or timezone.now()
    cutoff = now - timedelta(hours=policy.reader_consolidation_hours)
    period_start = now - timedelta(days=policy.reader_period_days)
    current_like = TbCronicaCurtida.objects.filter(
        cronica_id=OuterRef('cronica_id'), leitor_id=OuterRef('reader_id'),
    )
    groups = (SocialCreditReaderRecognition.objects.filter(
        policy=policy, first_seen_at__lte=cutoff,
        cronica__status='aprovada', cronica__data_publicacao__isnull=False,
        cronica__autor__is_active=True, reader__is_active=True,
    ).annotate(current_like=Exists(current_like)).filter(current_like=True)
        .values('cronica_id', 'cronica__autor_id')
        .annotate(readers=Count('pk')).order_by('cronica_id'))
    author_spent = {}
    preview = []
    amount = policy.reader_milestone_amount
    for group in groups:
        story_id = group['cronica_id']
        author_id = group['cronica__autor_id']
        if author_id not in author_spent:
            author_spent[author_id] = (SocialCreditEntry.objects.filter(
                wallet__user_id=author_id, kind='reader_milestone',
                created_at__gte=period_start, created_at__lte=now,
            ).aggregate(total=Sum('delta'))['total'] or 0)
        paid = SocialCreditEntry.objects.filter(
            kind='reader_milestone', wallet__user_id=author_id,
            operation_ref__startswith=f'chronicle:{story_id}:reader_milestone:',
        )
        story_spent = paid.aggregate(total=Sum('delta'))['total'] or 0
        prior_milestones = paid.filter(policy=policy).count()
        due = max(0, group['readers'] // policy.reader_milestone_size - prior_milestones)
        story_slots = max(0, (policy.reader_story_credit_cap - story_spent) // amount)
        author_slots = max(0, (policy.reader_author_period_credit_cap
                               - author_spent[author_id]) // amount)
        ready = min(due, story_slots, author_slots)
        author_spent[author_id] += ready * amount
        preview.append({
            'chronicle_id': story_id, 'author_id': author_id,
            'consolidated_readers': group['readers'],
            'milestones_due': due, 'milestones_ready': ready,
            'credits_ready': ready * amount,
        })
    return preview
