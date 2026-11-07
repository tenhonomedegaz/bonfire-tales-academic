"""Data-driven staff overrides; keep telemetry intact and MM delivery exactly once."""
import csv
import io
import json
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .master_legacy import _owner, normalized, quest_local_date, require_admin
from .master_mission_archive import digest, title_key
from .mission_reward_context import mission_details, reward_context
from .models import (BotDedicatedRank, BotQuest, TbAventuraMestre, TbMestreLegado,
                     TbPerfilMestre, TbRegistroMestreLegado, TbRevisaoMissaoBot,
                     TbTransacaoMestre, UserProfile)


def array(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
        return next(csv.reader(io.StringIO(value[1:-1])), [])
    return []


def quote_reward(quest, adventures, role_names):
    """Mirror questEmbeds.ts: override * 100 + capped pinned dedicated-rank bonus."""
    ranks, bonus, rank_id = array(quest.allowedRanks), 0, None
    if len(ranks) == 1:
        if ranks[0] not in role_names:
            raise ValidationError('Nome do cargo do rank ausente; consultar os cargos do Discord.')
        rank = BotDedicatedRank.objects.filter(pk=quest.dedicatedRankId, guildId=quest.guildId).first() if quest.dedicatedRankId else None
        if not rank:
            historical = list(BotDedicatedRank.objects.filter(guildId=quest.guildId,
                validFrom__lte=quest.questDate, validUntil__gte=quest.questDate)[:2])
            if len(historical) != 1:
                raise ValidationError('Rank historico ausente ou ambiguo; nao usar o rank de hoje.')
            rank = historical[0]
        rank_id = rank.pk
        reward = next((r for r in rank.rankings if r.get('rankName') == role_names[ranks[0]]), None)
        if reward:
            rate, cap = reward.get('rewardPerProgression'), reward.get('maxTotalReward')
            if type(rate) is not int or type(cap) is not int or min(rate, cap) < 0:
                raise ValidationError('Regra do rank historico invalida.')
            bonus = min(adventures * rate, cap)
    mm = adventures * 100 + bonus
    event = any(str(tag).lower() == 'evento' for tag in array(quest.tags))
    return {'mm': mm, 'event_coins': mm // 100 if event else 0,
            'base': adventures * 100, 'dedicated_bonus': bonus, 'rank_id': rank_id}


def snapshot(quest):
    values = {key: getattr(quest, key) for key in ('id', 'guildId', 'name', 'questMaster', 'questDate',
        'status', 'isPublished', 'rewardAventurasOverride', 'dedicatedRankId', 'allowedRanks', 'tags', 'updatedAt')}
    return {key: value.isoformat() if hasattr(value, 'isoformat') else value for key, value in values.items()}


def place_key(quest):
    value = urlsplit(quest.tableUrl or '')
    return digest([value.scheme.lower(), value.netloc.lower(), value.path.rstrip('/')]) if value.netloc else None


def preview(payload):
    allowed = {'import_id', 'guild_id', 'items', 'role_names', 'base_version'}
    items, guild = payload.get('items'), payload.get('guild_id')
    roles = payload.get('role_names', {})
    if (set(payload) - allowed or type(payload.get('import_id')) is not int
            or not isinstance(guild, str) or _owner(guild) != guild
            or not isinstance(items, list) or not 1 <= len(items) <= 40
            or not isinstance(roles, dict) or len(roles) > 100
            or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 150 for k, v in roles.items())):
        raise ValidationError('Lote de revisao invalido; exige import_id, guild_id e 1..40 itens.')
    query = BotQuest.objects.filter(guildId=guild)
    if query.count() > 20000:
        raise ValidationError('Escopo maior que 20000 missoes.')
    quests = list(query.only('id', 'guildId', 'name', 'questMaster', 'questDate', 'status', 'isPublished',
        'rewardAventurasOverride', 'dedicatedRankId', 'allowedRanks', 'tags', 'updatedAt', 'tableUrl'))
    by_id, rows, seen = {q.pk: q for q in quests}, [], set()
    for item in items:
        if (not isinstance(item, dict) or set(item) - {'quest_id', 'decision', 'adventures', 'master_mm',
            'event_coins', 'financial_mode', 'legacy_key', 'master_number', 'master_name', 'canonical_id', 'note', 'event',
            'reward_context', 'mission_details'}):
            raise ValidationError('Campos de revisao nao permitidos.')
        qid, decision = item.get('quest_id'), item.get('decision')
        if not isinstance(qid, str) or qid in seen or qid not in by_id:
            raise ValidationError('Missao repetida, ausente ou de outro servidor.')
        seen.add(qid)
        quest = by_id[qid]
        if 'event' in item and type(item['event']) is not bool:
            raise ValidationError('Marcador de evento deve ser booleano.')
        if decision not in ('confirmed', 'settled', 'duplicate', 'no_record', 'identity'):
            raise ValidationError('Decisao invalida.')
        adventures = item.get('adventures')
        if (adventures is not None and (type(adventures) is not int or not 0 <= adventures <= 100)
                or decision in ('confirmed', 'settled') and adventures is None):
            raise ValidationError('Quantidade de aventuras invalida.')
        mode = item.get('financial_mode', 'none')
        if mode not in ('none', 'baseline', 'new', 'settled') or (mode == 'new' and decision != 'confirmed'):
            raise ValidationError('Modo financeiro invalido.')
        if decision in ('duplicate', 'no_record', 'identity') and mode != 'none':
            raise ValidationError('Identificacao, duplicata ou sem registro nao concede moedas.')
        if decision in ('duplicate', 'no_record') and adventures not in (None, 0):
            raise ValidationError('Duplicatas e sem registro nao recebem aventuras.')
        name, note = item.get('master_name', ''), item.get('note', '')
        if not isinstance(name, str) or len(name) > 150 or not isinstance(note, str) or not 1 <= len(note) <= 800:
            raise ValidationError('Informe justificativa e nome de mestre valido.')
        master = record = None
        if item.get('legacy_key'):
            record = TbRegistroMestreLegado.objects.select_related('mestre').filter(
                mestre__importacao_id=payload['import_id'], chave=item['legacy_key'], tipo='adventure').first()
            if not record:
                raise ValidationError('Lancamento da planilha nao encontrado.')
            master = record.mestre
        if item.get('master_number') is not None:
            if type(item['master_number']) is not int:
                raise ValidationError('Numero da Fogueira deve ser inteiro.')
            chosen = TbMestreLegado.objects.filter(importacao_id=payload['import_id'], numero=item['master_number']).first()
            if not chosen or master and master.pk != chosen.pk:
                raise ValidationError('Fogueira nao corresponde ao lancamento.')
            master = chosen
        if master and master.discord_id and master.discord_id != _owner(quest.questMaster):
            raise ValidationError('Mestre confirmado diverge do autor da missao.')
        mm, coins, quote = item.get('master_mm'), item.get('event_coins'), None
        if mm is None and mode in ('new', 'baseline'):
            quote = quote_reward(quest, adventures, roles)
            mm = quote['mm']
        if coins is None:
            coins = (quote['event_coins'] if quote else
                     mm // 100 if mm is not None and any(str(t).lower() == 'evento' for t in array(quest.tags)) else 0)
            if 'event' in item and mm is not None:
                coins = mm // 100 if item['event'] else 0
                if quote:
                    quote['event_coins'] = coins
        if (mm is not None and (type(mm) is not int or not 0 <= mm <= 100000)
                or type(coins) is not int or not 0 <= coins <= 10000):
            raise ValidationError('Valores de moeda invalidos.')
        if mode == 'baseline' and (not record or mm != record.valor_mm):
            raise ValidationError('Credito ja importado deve corresponder ao valor da planilha.')
        linked = list(TbRegistroMestreLegado.objects.filter(bot_quest_id=qid))
        if mode == 'new' and (linked or record):
            raise ValidationError('Missao ja pertence a saldo legado; novo credito recusado.')
        if mode == 'new' and not _owner(quest.questMaster):
            raise ValidationError('Novo credito exige ID Discord de mestre valido.')
        canonical = by_id.get(item.get('canonical_id'))
        if decision == 'duplicate' and (not canonical or canonical.pk == qid or canonical.questMaster != quest.questMaster):
            raise ValidationError('Missao canonica ausente, igual ou de outro mestre.')
        if canonical and TbRevisaoMissaoBot.objects.filter(quest_id=canonical.pk, decision='duplicate').exists():
            raise ValidationError('Destino ja e uma duplicata; usar a missao canonica.')
        prior = TbRevisaoMissaoBot.objects.filter(quest_id=qid).first()
        if prior and prior.receipt_id and (mode != prior.financial_mode or mm != prior.master_mm or coins != prior.event_coins):
            raise ValidationError('Credito ja entregue: exige ajuste financeiro separado.')
        if prior and prior.financial_mode == 'new' and mode != 'new':
            raise ValidationError('Credito reservado nao pode ser descartado por revisao simples.')
        context = (prior.evidence or {}).get('reward_context') if prior else None
        details = (prior.evidence or {}).get('mission_details') if prior else None
        if 'reward_context' in item:
            context = reward_context(item['reward_context'], adventures=adventures, master_mm=mm)
        elif context is not None:
            context = reward_context(context, adventures=adventures, master_mm=mm)
        if 'mission_details' in item:
            details = mission_details(item['mission_details'], guild_id=guild)
        if context is not None and decision not in ('confirmed', 'settled'):
            raise ValidationError('Apenas missao confirmada pode manter contexto de recompensa.')
        same = [q for q in quests if q.pk != qid and q.questMaster == quest.questMaster and
                title_key(q.name) == title_key(quest.name) and
                (quest_local_date(q.questDate) == quest_local_date(quest.questDate) or
                 place_key(quest) and place_key(q) == place_key(quest))]
        rows.append({'quest_id': qid, 'title': quest.name, 'before': snapshot(quest), 'decision': decision,
            'adventures': adventures, 'master_name': name, 'master_mm': mm, 'event_coins': coins,
            'financial_mode': mode, 'canonical_id': canonical.pk if canonical else '',
            'legacy_master_id': master.pk if master else None, 'legacy_record_id': record.pk if record else None,
            'source_mm': record.valor_mm if record else None, 'source_bot_id': record.bot_quest_id if record else None,
            'quote': quote, 'note': note, 'same_name_place': [q.pk for q in same],
            'event': item.get('event'),
            'reward_context': context, 'mission_details': details,
            'prior': [prior.pk, prior.receipt_id, prior.decision, prior.reviewed_at.isoformat()] if prior else None})
    return {'base_version': digest(rows), 'rows': rows}


def _deliver(review, user, quest):
    if review.financial_mode != 'new' or review.receipt_id:
        return
    profile = UserProfile.objects.select_for_update().get(user=user)
    mm, coins = review.master_mm or 0, review.event_coins
    profile.moedas_mestragem += mm
    profile.moedas_evento += coins
    profile.mm_ganhas_total += mm
    profile.save(update_fields=['moedas_mestragem', 'moedas_evento', 'mm_ganhas_total'])
    review.receipt = TbTransacaoMestre.objects.create(mestre=user, tipo='aventura', valor_mm=mm,
        saldo_mm=profile.moedas_mestragem, descricao=f'[bot:{quest.pk}] {quest.name}'[:255])
    review.adventure_receipt = TbAventuraMestre.objects.create(mestre=user, nome=quest.name[:200],
        data=quest_local_date(quest.questDate), recompensa_mm=mm,
        observacao=f'Revisao administrativa do bot {quest.pk}; {review.adventures} aventuras')
    review.credit_user = user
    review.save(update_fields=['receipt', 'adventure_receipt', 'credit_user'])


@transaction.atomic
def apply(payload, *, actor):
    require_admin(actor)
    # Lock accounts before identities and review rows, matching OAuth/wallet writers.
    owner_ids = BotQuest.objects.filter(id__in=[r['quest_id'] for r in payload['items']]).values_list('questMaster', flat=True)
    user_ids = set(get_user_model().objects.filter(profile__discord_user_id__in=owner_ids).values_list('pk', flat=True))
    user_ids.update(TbMestreLegado.objects.filter(importacao_id=payload['import_id']).exclude(
        user_id=None).values_list('user_id', flat=True))
    list(get_user_model().objects.select_for_update().filter(pk__in=user_ids).order_by('pk'))
    list(TbMestreLegado.objects.select_for_update().filter(importacao_id=payload['import_id']).order_by('pk'))
    plan = preview(payload)
    if plan['base_version'] != payload['base_version']:
        raise ValidationError('Missao ou revisao mudou; consultar nova previa.')
    by_item = {r['quest_id']: r for r in plan['rows']}
    for row in plan['rows']:
        if row['decision'] == 'duplicate' and by_item.get(row['canonical_id'], {}).get('decision') == 'duplicate':
            raise ValidationError('Duplicata nao pode apontar para outra duplicata.')
    result = []
    for row in plan['rows']:
        quest = BotQuest.objects.select_for_update().get(pk=row['quest_id'])
        defaults = {k: row[k] for k in ('decision', 'adventures', 'master_name', 'master_mm', 'event_coins',
                                      'financial_mode', 'canonical_id', 'legacy_master_id', 'legacy_record_id')}
        defaults.update(guild_id=quest.guildId, master_discord_id=_owner(quest.questMaster) or '',
            reviewed_by=actor, evidence={'before': row['before'],
                                       'note': row['note'], 'quote': row['quote'], 'event': row['event']})
        for key in ('reward_context', 'mission_details'):
            if row[key] is not None:
                defaults['evidence'][key] = row[key]
        review, _ = TbRevisaoMissaoBot.objects.update_or_create(quest_id=quest.pk, defaults=defaults)
        fields = []
        if row['decision'] in ('confirmed', 'settled'):
            quest.status, quest.rewardAventurasOverride = 'finished', row['adventures']
            fields += ['status', 'rewardAventurasOverride']
        elif row['decision'] in ('duplicate', 'no_record'):
            quest.rewardAventurasOverride = 0
            fields.append('rewardAventurasOverride')
            quest.isPublished = False
            fields.append('isPublished')
        if fields:
            quest.updatedAt = timezone.now()
            quest.save(update_fields=fields + ['updatedAt'])
        if row['event'] is not None:
            tags = [str(t) for t in array(quest.tags) if str(t).lower() != 'evento']
            if row['event']:
                tags.append('evento')
            quest.tags = '{' + ','.join(json.dumps(t, ensure_ascii=False) for t in tags) + '}'
            quest.updatedAt = timezone.now()
            quest.save(update_fields=['tags', 'updatedAt'])
        if review.legacy_record_id:
            record = review.legacy_record
            old_id = record.bot_quest_id
            if old_id and old_id != quest.pk:
                old = BotQuest.objects.filter(pk=old_id).first()
                if old and old.createdBy == 'legacy-import' and old.type == 'legacy':
                    TbRevisaoMissaoBot.objects.update_or_create(quest_id=old.pk, defaults={
                        'guild_id': old.guildId, 'master_discord_id': _owner(quest.questMaster) or '',
                        'decision': 'duplicate', 'canonical_id': quest.pk, 'financial_mode': 'none',
                        'adventures': 0, 'reviewed_by': actor, 'evidence': {'source': record.chave}})
                elif not (old_id in by_item and by_item[old_id]['canonical_id'] == quest.pk):
                    raise ValidationError('Lancamento ja ligado a outra missao nativa; revisar duplicidade.')
            record.bot_quest_id = quest.pk
            record.save(update_fields=['bot_quest_id'])
        candidates = list(get_user_model().objects.filter(profile__discord_user_id=review.master_discord_id, is_active=True)[:2])
        if len(candidates) > 1:
            raise ValidationError('Discord associado a contas ambiguas.')
        user = candidates[0] if candidates else None
        if review.legacy_master_id and review.legacy_master.user_id:
            if user and user.pk != review.legacy_master.user_id:
                raise ValidationError('Conta verificada diverge do vinculo administrativo existente.')
            user = review.legacy_master.user
        if user and user.is_active:
            _deliver(review, user, quest)
        result.append({'quest_id': quest.pk, 'decision': review.decision, 'adventures': review.adventures,
            'master_mm': review.master_mm, 'event_coins': review.event_coins,
            'financial_mode': review.financial_mode, 'credited': bool(review.receipt_id),
            'pending_account': review.financial_mode == 'new' and not review.receipt_id})
    return {'rows': result}


@transaction.atomic
def claim_review_rewards(user, discord_id):
    if not user.is_active or not UserProfile.objects.filter(user=user, discord_user_id=discord_id).exists():
        return 0
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    trusted = TbRevisaoMissaoBot.objects.filter(master_discord_id=discord_id,
        decision__in=['identity', 'confirmed', 'settled'])
    from .master_legacy import _bind
    for master in TbMestreLegado.objects.select_for_update().filter(
            pk__in=trusted.exclude(legacy_master=None).values_list('legacy_master_id', flat=True)).order_by('pk'):
        if master.user_id in (None, user.pk) and master.discord_id in ('', discord_id):
            _bind(master, user)
    if trusted.exists():
        participation, _ = TbPerfilMestre.objects.get_or_create(user=user)
        if participation.status_mestre not in ('suspenso', 'recusado'):
            participation.status_mestre = 'aprovado'
            if participation.modo == 'jogador':
                participation.modo = 'ambos'
            participation.save(update_fields=['status_mestre', 'modo', 'atualizado_em'])
    reviews = list(TbRevisaoMissaoBot.objects.select_for_update().filter(master_discord_id=discord_id,
        financial_mode='new', receipt__isnull=True).order_by('pk')[:500])
    for review in reviews:
        if review.credit_user_id not in (None, user.pk):
            continue
        quest = BotQuest.objects.get(pk=review.quest_id)
        _deliver(review, user, quest)
    return len(reviews)
