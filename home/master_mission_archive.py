"""Private legacy mission records and bounded bot audits, without issuing rewards."""
import hashlib
import json
import re
from datetime import datetime, time, timezone as utc_timezone

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .master_legacy import _master_name, _number, _owner, normalized, quest_local_date, require_admin
from .models import BotQuest, TbImportacaoMestre, TbRegistroMestreLegado, TbRevisaoMissaoBot


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def title_key(value):
    return re.sub(r'[\W_]+', ' ', normalized(value)).strip()


def active_seconds(events):
    """Use the bot's run-to-next-event accounting; never invent missing duration."""
    if not isinstance(events, list) or len(events) > 5000:
        return 0, False
    parsed = []
    for event in events:
        if not isinstance(event, dict) or event.get('eventType') not in ('run', 'pause', 'freeze', 'finish'):
            return 0, False
        try:
            stamp = parse_datetime(event.get('date', '')) if isinstance(event.get('date'), str) else None
        except ValueError:
            stamp = None
        if not stamp:
            return 0, False
        if timezone.is_naive(stamp):
            stamp = stamp.replace(tzinfo=utc_timezone.utc)
        if parsed and stamp < parsed[-1][1]:
            return 0, False
        if parsed and event['eventType'] == parsed[-1][0] == 'run':
            return 0, False
        parsed.append((event['eventType'], stamp))
    seconds = sum((b[1] - a[1]).total_seconds() for a, b in zip(parsed, parsed[1:]) if a[0] == 'run')
    return int(seconds), not parsed or parsed[-1][0] != 'run'


def mission_audit(archive_id, guild_id, *, after_id='', limit=50):
    archive = TbImportacaoMestre.objects.get(pk=archive_id)
    masters = list(archive.mestres.only('numero', 'nome', 'discord_id'))
    query = BotQuest.objects.filter(guildId=guild_id)
    version = query.aggregate(count=Count('id'), updated=Max('updatedAt'))
    page = list(query.filter(id__gt=after_id).order_by('id').only(
        'id', 'name', 'questMaster', 'questDate', 'status', 'isPublished', 'timeEvents', 'channelId')[:limit + 1])
    ids = [q.pk for q in page[:limit]]
    legacy = dict(TbRegistroMestreLegado.objects.filter(mestre__importacao=archive,
        bot_quest_id__in=ids).values_list('bot_quest_id', 'mestre__numero'))
    decisions = {r.quest_id: r for r in TbRevisaoMissaoBot.objects.filter(quest_id__in=ids)}
    approved = list(TbRevisaoMissaoBot.objects.filter(guild_id=guild_id,
        master_discord_id__in=[q.questMaster for q in page[:limit]],
        decision__in=['identity', 'confirmed', 'settled']).select_related('legacy_master'))
    rows = []
    for quest in page[:limit]:
        owner = _owner(quest.questMaster)
        matching = [m for m in masters if owner and m.discord_id == owner]
        if not matching:
            matching = [m for m in masters if _number(quest.questMaster) == m.numero
                        or _master_name(quest.questMaster) == _master_name(m.nome)]
        numbers = sorted({m.numero for m in matching} | ({legacy[quest.pk]} if quest.pk in legacy else set()))
        aliases = [r for r in approved if r.master_discord_id == owner]
        numbers = sorted(set(numbers) | {r.legacy_master.numero for r in aliases if r.legacy_master_id})
        owner_state = ('identified' if len(numbers) == 1 else 'ambiguous' if numbers
                       else 'identified' if len({r.master_name for r in aliases if r.master_name}) == 1
                       else 'unmapped_discord' if owner else 'missing_or_unrecognized')
        seconds, valid = active_seconds(quest.timeEvents)
        reasons = []
        if normalized(quest.status) in ('cancelled', 'canceled', 'cancelada', 'cancelado', 'deleted'):
            reasons.append('cancelled')
        if not valid:
            reasons.append('invalid_time_events')
        if seconds <= 0:
            reasons.append('no_recorded_duration')
        if quest.status != 'finished' and 'cancelled' not in reasons:
            reasons.append('not_finished')
        review = decisions.get(quest.pk)
        if review and review.decision in ('duplicate', 'no_record'):
            reasons.append(review.decision)
        day = quest_local_date(quest.questDate)
        rows.append({'id': quest.pk, 'name': quest.name, 'date': day.isoformat() if day else None,
            'master': quest.questMaster, 'master_numbers': numbers, 'owner_state': owner_state,
            'status': quest.status, 'published': quest.isPublished, 'active_seconds': seconds,
            'duration_valid': valid, 'ineligible_reasons': reasons,
            'viable_for_review': not reasons, 'legacy_baseline_record': quest.pk in legacy,
            'staff_decision': review.decision if review else None,
            'canonical_id': review.canonical_id if review else None,
            'adventures_override': quest.rewardAventurasOverride,
            'master_name': next((r.master_name for r in aliases if r.master_name), None),
            'channel_id': quest.channelId})
    return {'import_id': archive.pk, 'guild_id': guild_id, 'total': version['count'],
            'source_revision': digest(version), 'rows': rows,
            'next_after_id': page[limit - 1].pk if len(page) > limit else None,
            'cancellation_coverage': 'Current rows only; the bot deletes cancelled missions. Discord logs are a separate source.'}


def backfill_plan(archive_id, checksum, guild_id, keys):
    archive = TbImportacaoMestre.objects.get(pk=archive_id)
    if archive.checksum != checksum:
        raise ValidationError('Checksum da planilha nao corresponde a importacao.')
    records = list(TbRegistroMestreLegado.objects.filter(mestre__importacao=archive,
        tipo='adventure', chave__in=keys).select_related('mestre').order_by('pk'))
    if len(records) != len(keys):
        raise ValidationError('Registro ausente, em quarentena ou nao e uma aventura.')
    query = BotQuest.objects.filter(guildId=guild_id)
    if query.count() > 20000:
        raise ValidationError('Mais de 20000 missoes; reduzir o escopo antes de importar.')
    quests = list(query.only('id', 'name', 'questMaster', 'questDate', 'updatedAt'))
    indexed = {}
    for quest in quests:
        indexed.setdefault((title_key(quest.name), quest_local_date(quest.questDate)), []).append(quest)
    by_id = {q.pk: q for q in quests}
    rows = []
    for record in records:
        if not record.data:
            raise ValidationError(f'Registro {record.pk} sem data; nao inventar data de missao.')
        if record.mestre.carteira_importada_em and not record.transacao_id:
            raise ValidationError(f'Registro {record.pk} sem recibo de carteira ja importada; revisar integridade.')
        target_id = 'legacy_' + digest([archive.checksum, record.chave])[:23]
        linked = by_id.get(record.bot_quest_id) if record.bot_quest_id else None
        if record.bot_quest_id and not linked:
            raise ValidationError(f'Registro {record.pk} tem vinculo ausente ou de outro servidor; revisar.')
        matches = indexed.get((title_key(record.titulo), record.data), [])
        if linked:
            action, bot_ids = 'already_linked', [linked.pk]
        elif matches:
            # A different/unresolved owner is evidence to review, never a reason to duplicate.
            action, bot_ids = 'review_existing', [q.pk for q in matches]
        elif target_id in by_id:
            raise ValidationError(f'ID legado ocupado sem vinculo no registro {record.pk}.')
        else:
            action, bot_ids = 'create_private_legacy', [target_id]
        rows.append({'record_id': record.pk, 'key': record.chave, 'number': record.mestre.numero,
            'title': record.titulo, 'date': record.data.isoformat(), 'action': action, 'bot_ids': bot_ids,
            'discord_id': record.mestre.discord_id,
            'financial_state': ('already_in_wallet' if record.transacao_id else
                                'pending_wallet_reconciliation' if record.mestre.user_id else 'reserved_in_legacy_balance')})
    version = digest({'source': checksum, 'guild': guild_id, 'rows': rows,
                      'bot': [(q.pk, q.name, q.questDate, q.questMaster, q.updatedAt) for q in sorted(quests, key=lambda q: q.pk)]})
    return {'import_id': archive.pk, 'base_version': version, 'rows': rows,
            'wallets_changed': False, 'new_credit_mm': 0}


@transaction.atomic
def backfill_apply(archive_id, checksum, guild_id, keys, base_version, *, actor):
    require_admin(actor)
    # Serialize archive imports; the API also serializes replay by its idempotency key.
    TbImportacaoMestre.objects.select_for_update().get(pk=archive_id)
    plan = backfill_plan(archive_id, checksum, guild_id, keys)
    if plan['base_version'] != base_version:
        raise ValidationError('O bot ou o vinculo mudou. Leia uma nova previa antes de importar.')
    now = timezone.now()
    created = 0
    for row in plan['rows']:
        if row['action'] != 'create_private_legacy':
            continue
        record = TbRegistroMestreLegado.objects.select_for_update().select_related('mestre').get(pk=row['record_id'])
        master = record.mestre
        metadata = {'origin': 'admin_validated_legacy_spreadsheet', 'import_id': archive_id,
            'source_key': record.chave, 'master_number': master.numero, 'approved_by': actor.pk,
            'date_precision': 'day', 'time_unknown': True,
            'financial_credit': 'included_in_legacy_balance_do_not_credit_again'}
        BotQuest.objects.create(id=row['bot_ids'][0], guildId=guild_id, channelId=None,
            name=record.titulo, description=json.dumps(metadata, ensure_ascii=False),
            questDate=timezone.make_aware(datetime.combine(record.data, time(12)), utc_timezone.utc),
            playersAmount=0, rules='Registro privado legado validado pela administracao; horario e duracao nao registrados.',
            tags='{}', type='legacy', tableUrl='',
            questMaster=master.discord_id or master.rotulo_original,
            allowedRanks='{}', mandatoryPlayers='{}', highPriorityPlayers='{}', removedPlayers='{}',
            createdBy='legacy-import', isPublished=False, status='finished', timeEvents=[],
            startDate=None, endDate=None, rewardAventurasOverride=0, createdAt=now, updatedAt=now)
        record.bot_quest_id = row['bot_ids'][0]
        record.save(update_fields=['bot_quest_id'])
        created += 1
    return {'import_id': archive_id, 'created': created, 'already_linked': sum(
            r['action'] == 'already_linked' for r in plan['rows']),
            'review_existing': [r for r in plan['rows'] if r['action'] == 'review_existing'],
            'wallets_changed': False, 'new_credit_mm': 0,
            'records': [{'key': r['key'], 'bot_ids': r['bot_ids'], 'action': r['action'],
                         'financial_state': r['financial_state']} for r in plan['rows']]}
