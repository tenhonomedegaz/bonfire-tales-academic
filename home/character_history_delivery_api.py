"""Explicit historical progress delivery; no build, gold or level-up automation."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .character_log_api import _actor, _invalid
from .character_log_models import CharacterLogSource, CharacterLogEntry
from .character_log_review import review_entry, entry_version
from .master_mission_archive import digest, backfill_plan, backfill_apply
from .models import BotQuest, TbMestreLegado, TbPersonagem, TbPersonagemAventura


def _plan(payload, actor):
    required = {'source_id', 'entry_key', 'title', 'date', 'master_number',
                'master_mm', 'mission_adventures', 'evidence'}
    if not isinstance(payload, dict) or set(payload) - (required | {'base_version'}) or not required <= set(payload):
        raise ValidationError('Informe fonte, entrada, missao comprovada, Fogueira, MM, aventuras e evidencia.')
    for key in ('source_id', 'master_number', 'master_mm', 'mission_adventures'):
        if type(payload[key]) is not int or not 1 <= payload[key] <= 100000:
            raise ValidationError('IDs e quantidades devem ser inteiros positivos limitados.')
    for key in ('entry_key', 'title', 'date', 'evidence'):
        if not isinstance(payload[key], str) or not 1 <= len(payload[key]) <= 2000:
            raise ValidationError('Texto de entrada invalido.')
    source = CharacterLogSource.objects.select_related('owner').get(pk=payload['source_id'])
    if source.metadata.get('history_authority') != 'registered_staff_log':
        raise ValidationError('Somente fonte oficial registrada e aprovada pela staff.')
    if source.owner.profile.discord_user_id != source.discord_user_id:
        raise ValidationError('Identidade Discord do dono mudou.')
    entries = list(source.entries.select_related('last_seen_batch').order_by('pk'))
    target = next((e for e in entries if e.source_key == payload['entry_key']), None)
    if not target or target.observed.get('title') != payload['title'] or target.observed.get('date') != payload['date']:
        raise ValidationError('Missao/data nao correspondem a entrada comprovada da fonte.')
    if target.observed.get('adventures') != payload['mission_adventures']:
        raise ValidationError('Aventuras da missao divergem do log aprovado.')
    master = TbMestreLegado.objects.get(numero=payload['master_number'])
    from .master_legacy import _master_name
    if not master.discord_id or _master_name(master.nome) != _master_name(target.observed.get('master')):
        raise ValidationError('Mestre do log exige Fogueira e Discord correspondentes.')
    candidates = list(TbPersonagem.objects.filter(dono=source.owner, nome__iexact=source.character_name)[:2])
    character = source.character or (candidates[0] if len(candidates) == 1 else None)
    if len(candidates) > 1 or (character and character.dono_id != source.owner_id):
        raise ValidationError('Personagem duplicado ou com outro dono; nao transferir automaticamente.')
    # Existing progress cannot safely be treated as uncredited historical progress.
    if character and (character.aventuras or character.aventuras_ledger.exists()):
        raise ValidationError('Ficha ja possui progresso; conciliar sobreposicao antes de creditar.')
    rows = []
    for e in entries:
        amount = payload['mission_adventures'] if e.pk == target.pk else e.adventures_confirmed
        if e.pk != target.pk and e.state not in ('matched', 'reviewed', 'staff_record'):
            raise ValidationError('Ha outra entrada pendente; resolver antes da entrega integral.')
        if type(amount) is not int or not 0 <= amount <= 100000:
            raise ValidationError('Quantidade desconhecida no historico.')
        rows.append({'entry_id': e.pk, 'version': entry_version(e), 'adventures': amount})
    from .master_roster import _history_title
    quests = BotQuest.objects.filter(guildId=target.last_seen_batch.snapshot['guild_id']).only('id','name')
    if quests.count() > 20000:
        raise ValidationError('Catalogo excede o limite de consulta; reduzir escopo antes da entrega.')
    matches = [q.pk for q in quests if _history_title(q.name) == _history_title(payload['title'])]
    if matches and not target.reference.startswith('bot:'):
        raise ValidationError('Missao candidata ja existe; revisar em vez de duplicar.')
    state = {'source': source.pk, 'owner': source.owner_id, 'discord': source.discord_user_id,
             'character': character.pk if character else None, 'rows': rows,
             'master': [master.pk, master.discord_id, master.saldo_mm, master.user_id],
             'payload': {k: payload[k] for k in sorted(required)}}
    return source, target, master, character, rows, {
        'base_version': digest(state), 'adventures': sum(r['adventures'] for r in rows),
        'declared_adventures': source.metadata.get('adventures_reported'),
        'character_id': character.pk if character else None, 'create_character_shell': character is None,
        'level_up': False, 'gold_credited': False, 'embers_credited': False,
        'master_discord_id': master.discord_id, 'master_mm': payload['master_mm']}


def history_delivery_preview(payload, api_key):
    actor = _actor(api_key)
    try:
        return _plan(payload, actor)[-1]
    except (ValidationError, CharacterLogSource.DoesNotExist, TbMestreLegado.DoesNotExist) as exc:
        raise _invalid(exc if isinstance(exc, ValidationError) else ValidationError('Fonte ou mestre ausente.')) from None


@transaction.atomic
def history_delivery_apply(payload, api_key):
    actor = _actor(api_key)
    if not isinstance(payload, dict):
        raise _invalid(ValidationError('Payload deve ser um objeto.'))
    try:
        # Lock before recalculating the financial/progression preview.
        source = CharacterLogSource.objects.get(pk=payload.get('source_id'))
        from django.contrib.auth import get_user_model
        get_user_model().objects.select_for_update().get(pk=source.owner_id)
        CharacterLogSource.objects.select_for_update().get(pk=source.pk)
        TbMestreLegado.objects.select_for_update().get(numero=payload.get('master_number'))
        source, target, master, character, rows, plan = _plan(payload, actor)
        if payload.get('base_version') != plan['base_version']:
            raise ValidationError('Previa mudou; nenhuma entrega aplicada.')
        from .master_legacy_api import _backup
        _backup()
        reviewed = review_entry(actor, target.pk, entry_version(target), 'register_missing_mission',
            title=payload['title'], date=payload['date'], master=master.nome,
            master_number=master.numero, master_mm=payload['master_mm'],
            adventures=payload['mission_adventures'], evidence=payload['evidence'],
            note='Entrega historica explicitamente autorizada; sem level-up e sem novo pagamento de ouro.')
        from .character_log_models import CharacterHistoryMission
        history = CharacterHistoryMission.objects.get(pk=reviewed.reference.split(':')[1])
        record = history.master_record
        guild = target.last_seen_batch.snapshot['guild_id']
        archive = master.importacao
        backfill = backfill_plan(archive.pk, archive.checksum, guild, [record.chave])
        backfill_apply(archive.pk, archive.checksum, guild, [record.chave], backfill['base_version'], actor=actor)
        record.refresh_from_db()
        if not record.bot_quest_id:
            raise ValidationError('Missao compartilhada nao vinculada; entrega recusada.')
        quest = BotQuest.objects.select_for_update().get(pk=record.bot_quest_id)
        if not isinstance(quest.questPlayers, list):
            raise ValidationError('Participantes da missao em formato invalido.')
        quest.questPlayers = [*quest.questPlayers, {
            'userId': source.discord_user_id, 'characterName': source.character_name,
            'characterUrl': 'https://docs.google.com/spreadsheets/d/'+source.spreadsheet_id+'/edit',
            'historicalLogSourceId': source.pk, 'rewardAmount':payload['mission_adventures'],
            'historicalImport':True}]
        quest.playersAmount = len(quest.questPlayers)
        quest.save(update_fields=['questPlayers', 'playersAmount'])
        review_entry(actor, reviewed.pk, entry_version(reviewed), 'link_mission',
            reference='bot:'+record.bot_quest_id, adventures=payload['mission_adventures'],
            note='Vinculo ao registro compartilhado do bot, com credito do mestre reservado na Fogueira.',
            evidence=payload['evidence'])
        if character is None:
            character = TbPersonagem.objects.create(dono=source.owner, nome=source.character_name,
                nivel=1, aventuras=0, publico=True,
                anotacoes='Historico legado importado; identidade mecanica e level-ups devem ser configurados pelo dono.')
        source.character = character
        source.save(update_fields=['character', 'updated_at'])
        by_id = {e.pk: e for e in source.entries.all()}
        for row in rows:
            entry = by_id[row['entry_id']]
            TbPersonagemAventura.objects.create(id_personagem=character,
                nome_aventura=entry.observed.get('title', '')[:200], qtd_aventuras=row['adventures'],
                origem='mesa' if entry.category == 'mission' else 'mercado_mestre' if entry.category == 'mm_redemption' else 'recompensa_comunidade',
                nivel_no_lancamento=character.nivel, criado_por=actor,
                detalhes_json={'contract':'historical-log-delivery:v1','source_id':source.pk,
                    'entry_id':entry.pk,'reference':entry.reference,
                    'history_authority':'registered_staff_log','previously_paid_economy':True})
        TbPersonagem.objects.filter(pk=character.pk).update(aventuras=F('aventuras')+plan['adventures'], atualizado_em=timezone.now())
        return {**plan, 'character_id':character.pk, 'bot_quest_id':record.bot_quest_id,
                'master_record_id':record.pk, 'master_credit':'reserved_in_fogueira',
                'character_level':character.nivel, 'history_entries':len(rows)}
    except (ValidationError, ValueError, OSError, CharacterLogSource.DoesNotExist,
            TbMestreLegado.DoesNotExist) as exc:
        raise _invalid(exc if isinstance(exc, ValidationError) else ValidationError('Backup/entrega historica recusado.')) from None
