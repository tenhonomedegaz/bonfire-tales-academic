"""Account credit ledger. Economic rules must be approved before callers issue credits."""

from datetime import timedelta
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Sum
from django.utils import timezone

from .models import (SocialCreditEntry, SocialCreditPolicy, SocialCreditReaderRecognition,
                     SocialCreditRedemption, SocialCreditWallet, TbCronica,
                     TbCronicaCurtida, TbPersonagem, TbPersonagemAventura)


def _validate_redemption_policy(policy):
    positive = ('redemption_cost', 'redemption_gold_pc', 'redemption_period_days',
                'redemption_period_limit', 'redemption_character_limit')
    if (not policy.active or not policy.redemption_enabled
            or any(type(getattr(policy, field)) is not int or getattr(policy, field) <= 0
                   for field in positive)
            or type(policy.redemption_counts_for_progression) is not bool
            or not policy.redemption_gold_source.strip()):
        raise ValueError('redemption policy is incomplete or inactive')


def redemption_quotes(user):
    """Show an approved offer for owned, active characters without reserving credits.

    This is deliberately read-only: the eventual debit and adventure delivery must
    share a transaction and enforce the policy limits again at commit time.
    """
    if not user.is_authenticated or not user.is_active:
        return []
    policy = SocialCreditPolicy.objects.filter(active=True, redemption_enabled=True).first()
    if policy is None:
        return []
    try:
        _validate_redemption_policy(policy)
    except ValueError:
        return []
    balance = (SocialCreditWallet.objects.filter(user=user)
               .values_list('balance', flat=True).first() or 0)
    period_start = timezone.now() - timedelta(days=policy.redemption_period_days)
    period_count = SocialCreditRedemption.objects.filter(
        user=user, created_at__gte=period_start).count()
    return [{
        'character': character,
        'cost': policy.redemption_cost,
        'gold_pc': policy.redemption_gold_pc,
        'gold_source': policy.redemption_gold_source,
        'progression': policy.redemption_counts_for_progression,
        'period_days': policy.redemption_period_days,
        'period_limit': policy.redemption_period_limit,
        'character_limit': policy.redemption_character_limit,
        'affordable': balance >= policy.redemption_cost,
        'within_period_limit': period_count < policy.redemption_period_limit,
        'within_character_limit': SocialCreditRedemption.objects.filter(
            character=character).count() < policy.redemption_character_limit,
        'policy_version': policy.version,
        'request_id': str(uuid4()),
    } for character in TbPersonagem.objects.filter(
        dono=user, arquivado=False).order_by('nome', 'pk')]


@transaction.atomic
def redeem_social_credit(user_id, character_id, request_id):
    """Debit and deliver once, with limits and ownership checked under account lock."""
    try:
        request_id = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('invalid redemption request id') from exc

    prior = SocialCreditRedemption.objects.filter(request_id=request_id).first()
    if prior:
        if prior.user_id != user_id or prior.character_id != character_id:
            raise ValueError('request id already belongs to another redemption')
        return prior, False

    policy = SocialCreditPolicy.objects.select_for_update().filter(
        active=True, redemption_enabled=True).first()
    if policy is None:
        raise ValueError('redemption is unavailable')
    _validate_redemption_policy(policy)
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if not user.is_active:
        raise ValueError('inactive account')
    prior = SocialCreditRedemption.objects.filter(request_id=request_id).first()
    if prior:
        if prior.user_id != user_id or prior.character_id != character_id:
            raise ValueError('request id already belongs to another redemption')
        return prior, False
    character = TbPersonagem.objects.select_for_update().get(pk=character_id)
    if character.dono_id != user_id or character.arquivado:
        raise ValueError('character is not eligible for redemption')

    period_start = timezone.now() - timedelta(days=policy.redemption_period_days)
    if SocialCreditRedemption.objects.filter(
            user=user, created_at__gte=period_start).count() >= policy.redemption_period_limit:
        raise ValueError('redemption period limit reached')
    if SocialCreditRedemption.objects.filter(
            character=character).count() >= policy.redemption_character_limit:
        raise ValueError('character redemption limit reached')

    credit, created = post_social_credit(
        user_id, operation_ref=f'redemption:{request_id}', kind='redemption',
        delta=-policy.redemption_cost, policy=policy,
    )
    if not created:
        raise ValueError('credit debit exists without a completed redemption')
    if policy.redemption_counts_for_progression:
        character.aventuras = int(character.aventuras or 0) + 1
    character.carteira_pc = int(character.carteira_pc or 0) + policy.redemption_gold_pc
    character.save(update_fields=['aventuras', 'carteira_pc', 'atualizado_em'])
    adventure = TbPersonagemAventura.objects.create(
        id_personagem=character, origem='recompensa_comunidade',
        nome_aventura='Resgate de aventura comunitária',
        qtd_aventuras=int(policy.redemption_counts_for_progression),
        ouro_pago_pc=policy.redemption_gold_pc,
        nivel_no_lancamento=int(character.nivel or 1),
        detalhes_json={
            'beneficio_aventuras': 1, 'credit_entry_id': credit.pk,
            'policy_version': policy.version, 'gold_source': policy.redemption_gold_source,
        },
    )
    from .market_services import register_transaction
    register_transaction(
        character, 'recompensa-social', 'Resgate de recompensa comunitária',
        policy.redemption_gold_pc,
        detalhes={'origem': 'recompensa_comunidade', 'adventure_ledger_id': adventure.pk,
                  'credit_entry_id': credit.pk},
    )
    redemption = SocialCreditRedemption.objects.create(
        request_id=request_id, user=user, character=character, policy=policy,
        credit_entry=credit, adventure_entry=adventure,
        cost=policy.redemption_cost, gold_pc=policy.redemption_gold_pc,
        gold_source=policy.redemption_gold_source,
        counts_for_progression=policy.redemption_counts_for_progression,
    )
    return redemption, True


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
        if policy is not None:
            try:
                _validate_reader_policy(policy)
            except ValueError:
                policy = None
    recognition, _ = SocialCreditReaderRecognition.objects.get_or_create(
        cronica=cronica, reader=reader, defaults={'policy': policy},
    )
    return recognition


def _validate_reader_policy(policy):
    fields = (
        'reader_milestone_size', 'reader_milestone_amount',
        'reader_consolidation_hours', 'reader_story_credit_cap',
        'reader_author_period_credit_cap', 'reader_period_days',
    )
    if not policy.reader_recognition_enabled or any(
        type(getattr(policy, field)) is not int or getattr(policy, field) <= 0
        for field in fields
    ):
        raise ValueError('reader recognition policy is incomplete or disabled')


def preview_reader_milestones(policy, *, as_of=None):
    """Read-only projection of consolidated reader milestones under one policy."""
    _validate_reader_policy(policy)
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


@transaction.atomic
def settle_reader_milestones(policy_id, story_id, *, as_of=None):
    """Post due milestones once, serializing against review and other author awards."""
    policy = SocialCreditPolicy.objects.select_for_update().get(pk=policy_id)
    if not policy.active:
        raise ValueError('reader recognition policy is not active')
    _validate_reader_policy(policy)
    story = TbCronica.objects.select_for_update().get(pk=story_id)
    if story.status != 'aprovada' or not story.data_publicacao:
        return []
    # An unlike must wait until this settlement has checked its current state.
    list(TbCronicaCurtida.objects.select_for_update().filter(
        cronica_id=story_id).values_list('pk', flat=True))
    get_user_model().objects.select_for_update().get(pk=story.autor_id)
    row = next((item for item in preview_reader_milestones(policy, as_of=as_of)
                if item['chronicle_id'] == story_id), None)
    if row is None or row['milestones_ready'] == 0:
        return []
    prefix = f'chronicle:{story_id}:reader_milestone:'
    prior = SocialCreditEntry.objects.filter(
        wallet__user_id=story.autor_id, policy=policy, kind='reader_milestone',
        operation_ref__startswith=prefix,
    ).count()
    entries = []
    for number in range(prior + 1, prior + row['milestones_ready'] + 1):
        entry, created = post_social_credit(
            story.autor_id,
            operation_ref=f'{prefix}{policy.pk}:{number}',
            kind='reader_milestone', delta=policy.reader_milestone_amount,
            policy=policy,
        )
        if created:
            entries.append(entry)
    return entries
