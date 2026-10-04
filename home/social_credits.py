"""Account credit ledger. Economic rules must be approved before callers issue credits."""

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import SocialCreditEntry, SocialCreditPolicy, SocialCreditWallet


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
