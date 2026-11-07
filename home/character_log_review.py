"""Evidence review never grants progress, money, event coins, or bot participation."""
import hashlib
import json
import re
from datetime import date as date_type

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .character_log_models import (CharacterHistoryMission, CharacterLogEntry, CharacterLogSource,
                                  CharacterLogMission, CharacterLogReview)
from .character_log_workbook import CATEGORY_LABELS, folded
from .gestao.policy import can
from .models import BotQuest, TbRegistroMestreLegado, TbRevisaoMissaoBot, TbTransacaoMestre


def require_reviewer(actor):
    if not can(actor, 'character_history.review'):
        raise PermissionDenied


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def entry_version(entry):
    return _digest([entry.pk, entry.observed_digest, entry.category, entry.state,
                    entry.reference, entry.adventures_confirmed, entry.updated_at])


def review_queue(actor, state='pending', q='', source_id=None):
    require_reviewer(actor)
    rows = CharacterLogEntry.objects.select_related('source__owner', 'last_seen_batch', 'reviewed_by')
    if state == 'pending':
        rows = rows.filter(state__in=['pending', 'stale'])
    elif state != 'all':
        if state not in {'matched', 'reviewed', 'rejected', 'stale', 'staff_record'}:
            raise ValidationError('Filtro de revisao invalido.')
        rows = rows.filter(state=state)
    if source_id:
        rows = rows.filter(source_id=source_id)
    if q:
        rows = rows.filter(Q(source__character_name__icontains=q[:150]) |
                           Q(observed__title__icontains=q[:150]))
    return rows.order_by('source__character_name', 'source_id', 'pk')


def _eligible_quests(guild):
    excluded = TbRevisaoMissaoBot.objects.filter(
        decision__in=['duplicate', 'no_record']).values('quest_id')
    rows = BotQuest.objects.filter(status='finished').exclude(pk__in=excluded)
    return rows.filter(guildId=guild) if guild else rows


def search_missions(actor, query, guild_id='', limit=20):
    require_reviewer(actor)
    query = str(query or '').strip()
    if not 2 <= len(query) <= 150:
        return []
    limit = min(max(int(limit), 1), 20)
    results = []
    for q in _eligible_quests(guild_id).filter(name__icontains=query).order_by('-questDate')[:limit]:
        results.append({'reference': f'bot:{q.pk}', 'title': q.name,
            'date': q.questDate.date().isoformat(), 'master': q.questMaster,
            'adventures': q.rewardAventurasOverride, 'origin': 'Missao do bot'})
    records = TbRegistroMestreLegado.objects.filter(tipo='adventure', titulo__icontains=query)
    if guild_id:
        records = records.filter(Q(bot_quest_id='') | Q(bot_quest_id__in=
            BotQuest.objects.filter(guildId=guild_id).values('id')))
    for r in records.select_related('mestre').order_by('-data', '-pk')[:limit]:
        results.append({'reference': f'legacy:{r.pk}', 'title': r.titulo,
            'date': r.data.isoformat() if r.data else '', 'master': r.mestre.nome,
            'adventures': None, 'origin': 'Registro validado da planilha'})
    manual = CharacterHistoryMission.objects.filter(title__icontains=query)
    if guild_id:
        manual = manual.filter(guild_id=guild_id)
    for r in manual.order_by('-date', '-pk')[:limit]:
        results.append({'reference': f'history:{r.pk}', 'title': r.title, 'date': r.date.isoformat(),
            'master': r.master_name, 'adventures': r.adventures, 'origin': 'Historico atestado pela staff'})
    return _with_characters(results[:limit])


def _with_characters(results):
    references = [r['reference'] for r in results]
    linked = CharacterLogEntry.objects.filter(reference__in=references, category='mission',
        state__in=['matched', 'reviewed']).select_related('source').order_by('source_id')
    people = {}
    for entry in linked:
        people.setdefault(entry.reference, {})[entry.source_id] = entry.source.character_name
    return [{**r, 'characters': list(people.get(r['reference'], {}).values())} for r in results]


def suggested_missions(actor, entry):
    require_reviewer(actor)
    if entry.category != 'mission':
        return []
    snapshot = entry.last_seen_batch.snapshot
    original = next((r for r in snapshot.get('rows', []) if r.get('key') == entry.source_key), {})
    ids = [r.get('id') for r in original.get('candidates', [])[:10] if isinstance(r, dict)]
    rows = _eligible_quests(snapshot.get('guild_id')).filter(pk__in=ids).order_by('name')
    return _with_characters([{'reference': f'bot:{r.pk}', 'title': r.name, 'date': r.questDate.date().isoformat(),
             'master': r.questMaster, 'adventures': r.rewardAventurasOverride,
             'origin': 'Titulo localizado na importacao; participacao/quantidade exigem conferencia'} for r in rows])


def search_redemptions(actor, entry, query='', limit=20):
    require_reviewer(actor)
    limit = min(max(int(limit), 1), 20)
    owner = entry.source.owner_id
    rows = TbTransacaoMestre.objects.filter(mestre_id=owner, tipo='resgate', valor_mm__lt=0)
    records = TbRegistroMestreLegado.objects.filter(
        tipo='purchase', mestre__user_id=owner)
    if query:
        rows = rows.filter(descricao__icontains=query[:150])
        records = records.filter(titulo__icontains=query[:150])
    results = [{'reference': f'mm:{r.pk}', 'title': r.descricao or 'Resgate MM',
                'date': r.criado_em.date().isoformat(), 'master': '', 'adventures': None,
                'origin': 'Recibo MM', 'mm_spent': -r.valor_mm}
               for r in rows.order_by('-criado_em')[:limit]]
    results += [{'reference': f'purchase:{r.pk}', 'title': r.titulo,
                 'date': r.data.isoformat() if r.data else '', 'master': '', 'adventures': None,
                 'origin': 'Resgate registrado na planilha', 'mm_spent': abs(r.valor_mm)}
                for r in records.order_by('-data')[:limit]]
    return results[:limit]


def _snapshot(entry):
    return {'category': entry.category, 'state': entry.state, 'reference': entry.reference,
            'adventures_confirmed': entry.adventures_confirmed,
            'observed_digest': entry.observed_digest}


def _reserve_master_record(actor, mission, number, amount, evidence):
    """Explicit admin-only supplement, reserved by Fogueira; no Discord guessing."""
    from .models import TbMestreLegado
    from .master_legacy import _master_name
    if not actor.is_superuser or type(number) is not int or type(amount) is not int or not 1 <= amount <= 100000:
        raise ValidationError('Registro de MM exige administrador, Fogueira e valor explicitos.')
    identities = list(TbMestreLegado.objects.select_for_update().filter(numero=number)[:2])
    if len(identities) != 1 or _master_name(identities[0].nome) != _master_name(mission.master_name):
        raise ValidationError('Fogueira e nome do mestre nao correspondem a uma identidade unica.')
    master = identities[0]
    if mission.master_record_id:
        record = mission.master_record
        if record.mestre_id != master.pk or record.valor_mm != amount:
            raise ValidationError('Esta missao ja possui outro registro financeiro; nao pagar novamente.')
        return record
    if master.user_id or master.carteira_importada_em:
        raise ValidationError('Mestre com carteira ativa exige o fluxo financeiro proprio; nao ajustar saldo por este historico.')
    from .master_roster import _history_title
    if any(_history_title(r.titulo) == _history_title(mission.title)
           for r in master.registros.filter(tipo='adventure')):
        raise ValidationError('Ja existe registro desse titulo para a Fogueira. Concilie antes de somar MM.')
    from .master_legacy_api import _backup
    try:
        _backup()
    except (ValueError, OSError):
        raise ValidationError('Backup financeiro indisponivel; nenhum registro ou saldo foi alterado.') from None
    record = TbRegistroMestreLegado.objects.create(mestre=master,
        chave='staff-history:' + mission.identity_key, tipo='adventure',
        titulo=mission.title, data=mission.date, valor_mm=amount,
        original={'source': 'staff_history_supplement', 'evidence': evidence,
                  'reviewed_by': actor.pk, 'history_mission_id': mission.pk,
                  'financial_mode': 'reserved_without_account'})
    master.saldo_mm += amount
    master.mesas_declaradas += 1
    master.save(update_fields=['saldo_mm', 'mesas_declaradas'])
    mission.master_record = record
    mission.save(update_fields=['master_record'])
    return record


def _reference(entry, reference, *, redemption=False):
    if not isinstance(reference, str) or len(reference) > 160 or ':' not in reference:
        raise ValidationError('Selecione um registro existente pelo buscador.')
    kind, key = reference.split(':', 1)
    guild = entry.last_seen_batch.snapshot.get('guild_id', '')
    if redemption:
        if kind == 'mm' and key.isdigit():
            receipt = TbTransacaoMestre.objects.filter(pk=key, mestre_id=entry.source.owner_id,
                                                     tipo='resgate', valor_mm__lt=0).first()
            valid = bool(receipt and (not receipt.personagem_id or
                         receipt.personagem_id == entry.source.character_id))
        elif kind == 'purchase' and key.isdigit():
            purchase = TbRegistroMestreLegado.objects.filter(pk=key, tipo='purchase',
                mestre__user_id=entry.source.owner_id).first()
            valid = bool(purchase)
            if purchase and purchase.transacao_id:
                return _reference(entry, f'mm:{purchase.transacao_id}', redemption=True)
        else:
            valid = False
    elif kind == 'bot':
        valid = _eligible_quests(guild).filter(pk=key).exists()
    elif kind == 'legacy' and key.isdigit():
        record = TbRegistroMestreLegado.objects.filter(pk=key, tipo='adventure').first()
        valid = bool(record and (not record.bot_quest_id or
            BotQuest.objects.filter(pk=record.bot_quest_id, guildId=guild).exists()))
    elif kind == 'history' and key.isdigit():
        valid = CharacterHistoryMission.objects.filter(pk=key, guild_id=guild).exists()
    else:
        valid = False
    if not valid:
        raise ValidationError('Registro indisponivel, cancelado ou fora do dono/servidor desta ficha.')
    return reference


@transaction.atomic
def review_entry(actor, entry_id, expected_version, action, *, reference='', category='',
                 note='', evidence='', adventures=None, title='', date='', master='',
                 master_number=None, master_mm=None):
    require_reviewer(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    require_reviewer(actor)
    initial = CharacterLogEntry.objects.select_related('source').get(pk=entry_id)
    get_user_model().objects.select_for_update().get(pk=initial.source.owner_id)
    source = CharacterLogSource.objects.select_for_update().get(pk=initial.source_id)
    entry = CharacterLogEntry.objects.select_for_update().select_related(
        'source', 'last_seen_batch').get(pk=entry_id)
    if source.owner_id != initial.source.owner_id:
        raise ValidationError('O dono da fonte mudou; recarregue a revisao.')
    if actor.pk == source.owner_id and not actor.is_superuser:
        raise PermissionDenied('Outro membro autorizado precisa revisar seu proprio historico.')
    if expected_version != entry_version(entry):
        raise ValidationError('O registro mudou. Recarregue a revisao antes de confirmar.')
    if action not in {'link_mission', 'link_redemption', 'verify_bonus',
                      'register_missing_mission', 'reject', 'reopen'}:
        raise ValidationError('Acao de revisao invalida.')
    if not isinstance(note, str) or not 5 <= len(note.strip()) <= 2000:
        raise ValidationError('Informe o motivo da revisao (5 a 2000 caracteres).')
    if not isinstance(evidence, str) or len(evidence) > 3000:
        raise ValidationError('Referencia de evidencia invalida.')
    if action not in {'reject', 'reopen'} and len(evidence.strip()) < 8:
        raise ValidationError('Informe a mensagem, recibo ou fonte que comprova esta entrada.')
    if adventures not in (None, ''):
        if not re.fullmatch(r'[0-9]{1,5}', str(adventures)):
            raise ValidationError('Quantidade confirmada deve ser um inteiro nao negativo.')
        adventures = int(adventures)
    else:
        adventures = None
    before = _snapshot(entry)
    if (master_number is not None or master_mm is not None) and action != 'register_missing_mission':
        raise ValidationError('Valores do mestre pertencem somente ao registro de missao ausente.')
    if action == 'link_mission':
        entry.reference = _reference(entry, reference)
        entry.category, entry.state = 'mission', 'reviewed'
    elif action == 'link_redemption':
        entry.reference = _reference(entry, reference, redemption=True)
        if entry.reference.startswith('mm:'):
            receipt = TbTransacaoMestre.objects.get(pk=entry.reference[3:])
            if receipt.quantidade is not None and adventures is not None and adventures > receipt.quantidade:
                raise ValidationError('Quantidade excede as aventuras do recibo. Concilie o lote sem duplicar recompensa.')
        entry.category, entry.state = 'mm_redemption', 'reviewed'
        # A debit can contain a bundle, but its allocation cannot be silently reused.
        if CharacterLogEntry.objects.exclude(pk=entry.pk).filter(
                reference=entry.reference).exclude(state='rejected').exists():
            raise ValidationError('Este recibo ja foi relacionado. Concilie o lote antes de reutiliza-lo.')
    elif action == 'verify_bonus':
        if category not in CATEGORY_LABELS or category == 'mission' or category == 'mm_redemption':
            raise ValidationError('Selecione a categoria de bonificacao ou troca de evento.')
        if category == 'event_exchange':
            if adventures is None or adventures < 1:
                raise ValidationError('Informe as aventuras do resgate associado a esta troca de evento.')
            reference = _reference(entry, reference, redemption=True)
        entry.category, entry.state = category, 'reviewed'
        # A legacy registered source already identifies the historical character.
        # No playable conversion is required just to reconcile old evidence.
        entry.reference = reference if category == 'event_exchange' else ''
    elif action == 'register_missing_mission':
        try:
            day = date_type.fromisoformat(str(date))
        except ValueError:
            raise ValidationError('Informe a data comprovada da missao ausente.') from None
        if not 2 <= len(title.strip()) <= 500 or not 2 <= len(master.strip()) <= 200:
            raise ValidationError('Informe titulo e mestre comprovados.')
        guild = entry.last_seen_batch.snapshot.get('guild_id', '')
        if not guild:
            raise ValidationError('A fonte nao informa o servidor Discord.')
        # Same historical mission is reused across character imports, never duplicated.
        from .master_roster import _history_title
        identity = _digest([guild, day.isoformat(), _history_title(title), folded(master)])
        old = CharacterHistoryMission.objects.filter(identity_key=identity).first()
        if old and old.adventures != adventures:
            raise ValidationError('A missao historica ja existe com outra quantidade; vincule e revise sem duplicar.')
        mission, _ = CharacterHistoryMission.objects.get_or_create(identity_key=identity,
            defaults={'title': title.strip(), 'date': day, 'master_name': master.strip(),
                      'guild_id': guild, 'adventures': adventures, 'evidence': evidence.strip(),
                      'created_by': actor})
        if mission.adventures != adventures:
            raise ValidationError('A missao historica ja existe com outra quantidade.')
        if master_number is not None or master_mm is not None:
            reserved = _reserve_master_record(actor, mission, master_number, master_mm, evidence.strip())
            mission.evidence += f'\nRegistro da Fogueira: {reserved.pk}; {reserved.valor_mm} MM reservados, sem conta creditada.'
            mission.save(update_fields=['evidence'])
        entry.category, entry.state, entry.reference = 'mission', 'reviewed', f'history:{mission.pk}'
    else:
        entry.state = 'rejected' if action == 'reject' else 'pending'
        entry.reference = ''
    if entry.source.character_id and entry.source.character.dono_id != entry.source.owner_id:
        raise ValidationError('O dono do personagem associado mudou. Revise a fonte primeiro.')
    entry.adventures_confirmed = adventures if action not in {'reject', 'reopen'} else None
    entry.reviewed_by, entry.reviewed_at = actor, timezone.now()
    entry.save()
    CharacterLogReview.objects.create(entry=entry, actor=actor, before=before, after=_snapshot(entry),
                                     note=note.strip(), evidence=evidence.strip())
    _sync_mission_links(entry.source)
    return entry


def _sync_mission_links(source):
    CharacterLogMission.objects.filter(source=source).update(needs_review=True)
    entries = source.entries.filter(state__in=['matched', 'reviewed'], category='mission',
                                     reference__startswith='bot:')
    for entry in entries:
        try:
            _reference(entry, entry.reference)
        except ValidationError:
            entry.state = 'stale'
            entry.save(update_fields=['state', 'updated_at'])
            continue
        CharacterLogMission.objects.update_or_create(source=source,
            bot_quest_id=entry.reference[4:], defaults={'last_seen_batch': entry.last_seen_batch,
                'evidence': entry.observed, 'needs_review': False})


def sync_entries(source, batch, rows):
    """Reimports keep manual decisions only when the observed source is unchanged."""
    seen = []
    for row in rows:
        observed = {k: v for k, v in row.items() if k not in
                    {'state', 'quest_id', 'proof', 'warnings', 'candidates'}}
        observed['history_authority'] = batch.snapshot.get('metadata', {}).get('history_authority', 'unverified_upload')
        digest = _digest(observed)
        entry, created = CharacterLogEntry.objects.get_or_create(source=source, source_key=row['key'],
            defaults={'last_seen_batch': batch, 'observed': observed, 'observed_digest': digest,
                      'category': row.get('category', 'mission')})
        seen.append(entry.pk)
        changed = entry.observed_digest != digest
        if changed:
            entry.state, entry.reference = 'stale', ''
            entry.adventures_confirmed = None
            entry.observed, entry.observed_digest = observed, digest
        if created or entry.reviewed_by_id is None:
            entry.category = row.get('category', 'mission')
            entry.state = ('matched' if row['state'] == 'matched' else
                           'staff_record' if row['state'] == 'staff_confirmed' else 'pending')
            entry.reference = f"bot:{row['quest_id']}" if row['state'] == 'matched' else ''
            entry.adventures_confirmed = (row.get('proof', {}).get('reward_amount')
                                          if row['state'] in ('matched', 'staff_confirmed') or
                                          observed.get('history_authority') == 'registered_staff_log' else None)
        entry.last_seen_batch = batch
        entry.save()
    source.entries.exclude(pk__in=seen).exclude(state='rejected').update(state='stale')
    _sync_mission_links(source)
