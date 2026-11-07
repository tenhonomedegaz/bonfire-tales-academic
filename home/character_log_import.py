"""Preview and reconcile registered bot sheets without issuing character rewards."""
import hashlib
import json
import re

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .character_log_models import CharacterLogImportBatch, CharacterLogMission, CharacterLogSource
from .character_log_workbook import download_workbook, folded, read_workbook, spreadsheet_id
from .master_legacy import quest_local_date
from .master_roster import _history_title
from .models import BotCharacterLog, BotQuest, TbPersonagem, TbRevisaoMissaoBot, UserProfile

SALT = 'bonfire.character-log-import.v1'
MAX_QUESTS = 2000


def _require(actor):
    if not actor or not actor.is_authenticated or not actor.is_active or not actor.is_superuser:
        raise PermissionDenied


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     ensure_ascii=True).encode()).hexdigest()


def _identity(log):
    source_id = spreadsheet_id(log.spreadsheetId)
    if not source_id or spreadsheet_id(log.sheetUrl) != source_id:
        raise ValidationError('O link e o identificador cadastrados no bot divergem.')
    owners = list(UserProfile.objects.filter(discord_user_id=log.discordUserId,
                                            user__is_active=True).select_related('user')[:2])
    if len(owners) != 1:
        raise ValidationError('Vincule primeiro este Discord a uma unica conta ativa do site.')
    return owners[0].user, source_id


def registered_logs(actor, discord_id):
    _require(actor)
    if not isinstance(discord_id, str) or not re.fullmatch(r'[0-9]{15,22}', discord_id):
        raise ValidationError('Informe o ID Discord do jogador, nao o nome de exibicao.')
    logs = list(BotCharacterLog.objects.filter(discordUserId=discord_id).order_by('characterName', 'id')[:101])
    if len(logs) > 100:
        raise ValidationError('Mais de 100 fichas neste Discord; refine o cadastro antes de importar.')
    return logs


def _quest_rows(guild_id):
    if guild_id:
        if not isinstance(guild_id, str) or not re.fullmatch(r'[0-9]{15,22}', guild_id):
            raise ValidationError('ID do servidor Discord invalido.')
    else:
        guilds = list(BotQuest.objects.values_list('guildId', flat=True).distinct()[:2])
        if len(guilds) != 1:
            raise ValidationError('Informe o servidor Discord para nao cruzar comunidades.')
        guild_id = guilds[0]
    excluded = TbRevisaoMissaoBot.objects.filter(
        guild_id=guild_id, decision__in=['duplicate', 'no_record']).values('quest_id')
    quests = list(BotQuest.objects.filter(guildId=guild_id, status='finished').exclude(
        type='legacy').exclude(createdBy='legacy-import').exclude(pk__in=excluded).only(
            'id', 'guildId', 'name', 'questMaster', 'questDate', 'endDate', 'questPlayers',
            'rewardAventurasOverride', 'timeEvents', 'updatedAt').order_by('id')[:MAX_QUESTS + 1])
    if len(quests) > MAX_QUESTS:
        raise ValidationError('Mais de 2000 missoes concluidas; a consulta precisa de um recorte de periodo.')
    return guild_id, quests


def _participant(quest, log):
    players = quest.questPlayers if isinstance(quest.questPlayers, list) else []
    entries = [p for p in players if isinstance(p, dict) and str(p.get('userId', '')) == log.discordUserId]
    if len(entries) != 1:
        return None
    player = entries[0]
    if player.get('removedAt') and not player.get('removedWithReward'):
        return None
    sheet = spreadsheet_id(player.get('characterUrl', ''))
    if sheet and sheet != log.spreadsheetId:
        return None
    name = player.get('characterName')
    if name and folded(name) != folded(log.characterName):
        return None
    if getattr(log, '_multiple_characters', False) and not (name or sheet):
        return None  # A Discord member with multiple sheets is not a character identity.
    return player


def _match(parsed, log, guild_id):
    guild_id, quests = _quest_rows(guild_id)
    staff_history = parsed.get('metadata', {}).get('history_authority') == 'registered_staff_log'
    log._multiple_characters = BotCharacterLog.objects.filter(discordUserId=log.discordUserId).exclude(
        spreadsheetId=log.spreadsheetId).exists()
    from .character_log_matching import candidates_for, reward_for
    from .models import TbMestreLegado
    masters = list(TbMestreLegado.objects.values_list('nome', 'discord_id'))
    relevant = {}
    rows = []
    for entry in parsed['rows']:
        row = {**entry, 'state': 'adjustment' if entry['kind'] != 'mission' else 'unmatched',
               'candidates': [], 'quest_id': '', 'warnings': []}
        if staff_history:
            row['proof'] = {'history_authority': 'registered_staff_log',
                            'reward_amount': entry.get('adventures'), 'new_credit': False}
        if staff_history and entry['kind'] != 'mission':
            row.update(state='staff_confirmed', proof={'history_authority': 'registered_staff_log',
                'reward_amount': entry.get('adventures'), 'new_credit': False})
        if entry['kind'] == 'mission':
            candidates = candidates_for(entry, quests, masters)
            relevant.update({q.pk: q for q in candidates})
            proven = [q for q in candidates if _participant(q, log) is not None]
            if staff_history and not proven:
                # Legacy staff-approved sheets predate native participant tracking.
                proven = candidates
            if len(proven) > 1 and entry['date']:
                dated = [q for q in proven if entry['date'] in {
                    str(quest_local_date(q.questDate)), str(quest_local_date(q.endDate)) if q.endDate else ''}]
                if len(dated) == 1:
                    proven = dated
            row['candidates'] = [{'id': q.pk, 'title': q.name,
                                  'date': str(quest_local_date(q.questDate))} for q in candidates[:10]]
            if len(proven) == 1:
                quest = proven[0]
                player = _participant(quest, log)
                amount, quantity_proof = reward_for(entry, quest, player)
                bot_amount = quantity_proof.get('base_adventures')
                if type(amount) is not int or not 0 <= amount <= 100000:
                    row.update(state='quantity_unproven', warnings=[
                        'Missao e participante encontrados, mas o bot nao comprova a quantidade de aventuras.'])
                elif not staff_history and entry['adventures'] is not None and entry['adventures'] != amount:
                    row.update(state='conflict', warnings=['Quantidade da planilha diverge do registro do bot.'])
                else:
                    row.update(state='matched', quest_id=quest.pk,
                               proof={'owner_in_bot': player is not None,
                                      'owner_from_staff_log': staff_history,
                                      'character_reference': bool((player or {}).get('characterName') or
                                                                  spreadsheet_id((player or {}).get('characterUrl', ''))),
                                      'history_authority': 'registered_staff_log' if staff_history else 'native_bot',
                                      'bot_reward_amount': bot_amount if type(bot_amount) is int else None,
                                      'reward_amount': amount, **quantity_proof})
                    if entry['adventures'] is not None and entry['adventures'] != amount:
                        row['warnings'].append('Quantidade divergente: saldo conciliado usa bot/duracao; declaracao original preservada.')
                    if entry['date'] and entry['date'] not in {
                            str(quest_local_date(quest.questDate)),
                            str(quest_local_date(quest.endDate)) if quest.endDate else ''}:
                        row['warnings'].append('Data divergente; titulo e participacao conferem, sem creditar recompensas.')
            elif candidates:
                row['state'] = 'ambiguous' if len(proven) > 1 else 'unproven'
        rows.append(row)
    # A sheet can repeat a session as adjustment/report. Never link twice or silently sum.
    repeated = {}
    for row in rows:
        if row['quest_id']:
            repeated.setdefault(row['quest_id'], []).append(row)
    for group in repeated.values():
        if len(group) > 1:
            for row in group:
                row.update(state='ambiguous', quest_id='')
                row['warnings'].append('A mesma missao aparece mais de uma vez na planilha.')
    version = _digest([{'id': q.pk, 'name': q.name, 'master': q.questMaster,
                        'date': q.questDate, 'end': q.endDate, 'players': q.questPlayers,
                        'amount': q.rewardAventurasOverride, 'events': q.timeEvents}
                       for q in relevant.values()] + [{'master_aliases': masters}])
    return guild_id, rows, version


def _stamp(log, owner):
    return _digest([log.pk, log.spreadsheetId, log.sheetUrl, log.discordUserId,
                    log.characterName, log.updatedAt, owner.pk])


def preview_log(actor, log_id, *, uploaded=None, guild_id=None):
    _require(actor)
    try:
        log = BotCharacterLog.objects.get(pk=log_id)
    except BotCharacterLog.DoesNotExist:
        raise ValidationError('Ficha nao encontrada no cadastro do bot.') from None
    owner, source_id = _identity(log)
    parsed = read_workbook(uploaded if uploaded is not None else download_workbook(source_id))
    parsed['metadata']['history_authority'] = ('registered_staff_log' if uploaded is None else 'unverified_upload')
    if folded(parsed['metadata']['character_name']) != folded(log.characterName):
        raise ValidationError('O nome na planilha diverge do personagem cadastrado no bot; confira a origem.')
    parsed['metadata']['bot_summary'] = {'class_name': log.className, 'rank_name': log.rankName,
                                       'level': log.level, 'adventures_reported': log.adventuresPlayed}
    for key, label in (('class_name', 'Classe'), ('rank_name', 'Rank'),
                       ('level', 'Nivel'), ('adventures_reported', 'Total de aventuras')):
        sheet_value, bot_value = parsed['metadata'][key], parsed['metadata']['bot_summary'][key]
        if sheet_value is not None and folded(sheet_value) != folded(bot_value):
            parsed['warnings'].append(f'{label}: planilha e resumo do bot divergem; ambos foram preservados.')
    guild_id, rows, version = _match(parsed, log, guild_id)
    parsed['metadata']['adventures_read'] = sum(row['adventures'] or 0 for row in rows)
    parsed['metadata']['adventures_reconciled'] = sum(
        row.get('proof', {}).get('reward_amount') or 0 for row in rows
        if row['state'] in ('matched', 'staff_confirmed'))
    parsed['metadata']['unknown_quantity_entries'] = sum(row['adventures'] is None for row in rows)
    if parsed['metadata']['adventures_reported'] is not None and not parsed['metadata']['unknown_quantity_entries']:
        if parsed['metadata']['adventures_read'] != parsed['metadata']['adventures_reported']:
            parsed['warnings'].append('A soma das entradas diverge do total declarado. Nao alterar o progresso automaticamente.')
    if uploaded is not None and any(row['category'] != 'mission' for row in rows):
        parsed['warnings'].append('Salarios, bonus e resgates sao entradas a comprovar, nao missoes automaticamente validadas.')
    # A unique name is only a suggestion inside the verified owner's account.
    characters = list(TbPersonagem.objects.filter(dono=owner, nome__iexact=log.characterName).values_list('pk', flat=True)[:2])
    payload = {'actor': actor.pk, 'log': log.pk, 'owner': owner.pk, 'spreadsheet_id': source_id,
               'stamp': _stamp(log, owner), 'guild_id': guild_id, 'match_version': version,
               'parsed': parsed, 'rows': rows, 'character_id': characters[0] if len(characters) == 1 else None,
               'input_kind': 'uploaded_xlsx' if uploaded is not None else 'registered_google_sheet'}
    # ZIP timestamps and a different reviewing admin do not create another import.
    fingerprint = _digest({key: value for key, value in payload.items()
                           if key not in ('actor', 'stamp', 'parsed')} | {
        'parsed': {key: value for key, value in parsed.items() if key != 'file_hash'}})
    payload['fingerprint'] = fingerprint
    ticket = signing.dumps(payload, salt=SALT, compress=True)
    if len(ticket) > 1500000:
        raise ValidationError('Previa excede o limite. Nenhum dado foi gravado.')
    return {'owner': owner, 'log': log, 'metadata': parsed['metadata'], 'rows': rows,
            'warnings': parsed['warnings'], 'matched': sum(r['state'] == 'matched' for r in rows),
            'pending': sum(r['state'] not in ('matched', 'staff_confirmed') for r in rows),
            'character_id': payload['character_id'], 'fingerprint': fingerprint, 'ticket': ticket}


@transaction.atomic
def apply_log(actor, ticket, *, expected_fingerprint=None):
    _require(actor)
    try:
        payload = signing.loads(ticket, salt=SALT, max_age=900)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Previa invalida ou expirada. Analise a planilha novamente.') from None
    if payload['actor'] != actor.pk:
        raise PermissionDenied
    if expected_fingerprint is not None and expected_fingerprint != payload['fingerprint']:
        raise ValidationError('A versao da previa nao corresponde a esta confirmacao.')
    current_actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    _require(current_actor)
    try:
        log = BotCharacterLog.objects.select_for_update().get(pk=payload['log'])
    except BotCharacterLog.DoesNotExist:
        raise ValidationError('O cadastro da ficha no bot nao esta mais disponivel.') from None
    owner, source_id = _identity(log)
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    if source_id != payload['spreadsheet_id'] or _stamp(log, owner) != payload['stamp']:
        raise ValidationError('O dono ou o cadastro da ficha mudou. Gere outra previa.')
    source = CharacterLogSource.objects.select_for_update().filter(spreadsheet_id=source_id).first()
    if source and (source.owner_id != owner.pk or source.discord_user_id != log.discordUserId):
        raise ValidationError('Fonte ja vinculada a outro dono; transferencia exige revisao separada.')
    if source and source.character_id and not TbPersonagem.objects.filter(pk=source.character_id, dono=owner).exists():
        raise ValidationError('O dono da ficha relacionada mudou. Revise o vinculo antes de importar.')
    prior = CharacterLogImportBatch.objects.filter(source=source, fingerprint=payload['fingerprint']).first() if source else None
    if prior:
        return prior
    _, rows, version = _match(payload['parsed'], log, payload['guild_id'])
    if version != payload['match_version'] or rows != payload['rows']:
        raise ValidationError('As missoes do bot mudaram. Gere outra previa antes de importar.')
    character_id = payload['character_id']
    if character_id and not TbPersonagem.objects.filter(pk=character_id, dono=owner,
                                                       nome__iexact=log.characterName).exists():
        raise ValidationError('O vinculo da ficha do site mudou. Gere outra previa.')
    metadata = {**payload['parsed']['metadata'], 'bot_adventures_reported': log.adventuresPlayed,
                'input_kind': payload['input_kind']}
    if source is None:
        source = CharacterLogSource.objects.create(spreadsheet_id=source_id, bot_log_id=log.pk,
            owner=owner, discord_user_id=log.discordUserId, character_name=log.characterName,
            character_id=character_id, metadata=metadata)
    else:
        if source.character_id and character_id and source.character_id != character_id:
            raise ValidationError('A fonte ja esta relacionada a outra ficha. Revise o vinculo explicitamente.')
        source.bot_log_id, source.character_name, source.metadata = log.pk, log.characterName, metadata
        if not source.character_id:
            source.character_id = character_id
        source.save(update_fields=['bot_log_id', 'character_name', 'metadata', 'character', 'updated_at'])
    batch = CharacterLogImportBatch.objects.create(source=source, fingerprint=payload['fingerprint'],
        actor=current_actor, snapshot={'format': payload['parsed']['format'],
            'file_hash': payload['parsed']['file_hash'], 'metadata': metadata,
            'guild_id': payload['guild_id'], 'rows': rows, 'warnings': payload['parsed']['warnings']})
    from .character_log_review import sync_entries
    sync_entries(source, batch, rows)
    return batch
