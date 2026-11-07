"""Public numbered identities; account registration is not a prerequisite."""
import json
import math
import re
from urllib.parse import urlsplit

from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render

from .master_legacy import _master_name, _owner, quest_local_date
from .master_mission_archive import active_seconds, title_key
from .master_registration import number_limit
from .models import BotQuest, TbMestreLegado, TbRegistroMestreLegado, TbRevisaoMissaoBot


def identities():
    return TbMestreLegado.objects.filter(numero__gte=1, numero__lte=number_limit()).select_related('user__profile', 'user__participacao').order_by('numero', '-pk')


def card(identity):
    from .master_participation import participation
    user = identity.user if identity.user_id and identity.user.is_active else None
    profile = getattr(user, 'participacao', None)
    visible = profile and profile.status_mestre == 'aprovado' and profile.listado
    return {'identity': identity, 'user': user, 'display_name': identity.nome,
            'initial': _master_name(identity.nome)[:1].upper(),
            'community': participation(profile) if visible else {'role_label': 'Mestre'},
            'portfolio_banner': profile.banner_portfolio_url if visible else ''}


def directory(request):
    search = request.GET.get('q', '').strip()[:120]
    rows = list(identities())
    # Older imports can contain another snapshot of the same numbered identity.
    rows = list({row.numero: row for row in reversed(rows)}.values())
    rows.sort(key=lambda row: row.numero)
    if search:
        wanted = _master_name(search)
        number = re.fullmatch(r'(?:f(?:ogueira)?\s*)?0*(\d+)', search, re.I)
        if number:
            rows = [row for row in rows if row.numero == int(number[1])]
        else:
            rows = [row for row in rows if wanted in _master_name(row.nome)
                    or search.casefold() in (row.user.username.casefold() if row.user_id else '')
                    or wanted in _master_name(str(card(row)['community'].get('estilo', '')))]
    page = Paginator(rows, 24).get_page(request.GET.get('pagina'))
    return render(request, 'home/pages/master_directory.html', {
        'masters': [card(row) for row in page], 'masters_page': page,
        'search': search, 'page_title': 'Mestres da comunidade'})


def _excluded(review):
    return bool(review and review.decision in ('duplicate', 'no_record'))


def adventure_amount(quest, review=None):
    if _excluded(review):
        return None
    if review and review.adventures is not None:
        return review.adventures
    if quest.status != 'finished':
        return None
    if quest.type == 'legacy':
        if quest.rewardAventurasOverride is not None and quest.rewardAventurasOverride > 0:
            return quest.rewardAventurasOverride
        return None  # Zero is an import sentinel, not evidence of zero adventures.
    if quest.rewardAventurasOverride is not None:
        return max(0, quest.rewardAventurasOverride)
    seconds, valid = active_seconds(quest.timeEvents)
    if not valid or seconds <= 0:
        return None
    minutes = seconds // 60
    # Same thresholds as the bot's questRewardAmount; view only, never a credit.
    amount = next((reward for threshold, reward in reversed([
        (150, 1), (300, 2), (450, 3), (600, 4), (900, 6), (1200, 8)]) if minutes >= threshold), 0)
    return amount + max(0, (minutes - 1200) // 600) * 4


def _history_title(value):
    # Keep chapter tokens (I, II, IV, ...) intact; only the English article is optional.
    return re.sub(r'^the\s+', '', title_key(value))


def _history_matches(records, quests, reviewed, *, names=None, guild_id=None):
    """Reconcile sources, not dates: reporting dates need not be session dates."""
    originals, imported = {}, {}
    for quest in quests.values():
        review = reviewed.get(quest.pk)
        if quest.type != 'legacy' and not _excluded(review):
            originals.setdefault(_history_title(quest.name), []).append(quest)
    record_reviews = {r.legacy_record_id: r for r in reviewed.values() if getattr(r, 'legacy_record_id', None)}
    for record in records:
        quest = quests.get(record.bot_quest_id)
        review = reviewed.get(record.bot_quest_id) or record_reviews.get(record.pk)
        if (not quest or quest.type == 'legacy') and not _excluded(review) and not record_reviews.get(record.pk):
            imported.setdefault(_history_title(record.titulo), []).append(record)
    matches = {}
    for title, rows in imported.items():
        candidates = originals.get(title, []) if title else []
        scoped = {}
        for record in rows:
            source = quests.get(record.bot_quest_id)
            guild = getattr(source, 'guildId', guild_id)
            owner = getattr(source, 'questMaster', None)
            eligible = []
            for quest in candidates:
                if names is not None and (guild is None or quest.questMaster not in names):
                    continue
                if guild is not None and getattr(quest, 'guildId', None) != guild:
                    continue
                same_owner = owner is None or (_owner(owner) or owner) == (_owner(quest.questMaster) or quest.questMaster)
                if not same_owner and not (names is not None and owner in names and quest.questMaster in names):
                    continue
                eligible.append(quest)
            scoped[record.pk] = eligible
        # Repeated titles require reciprocal, unique date evidence. Never take
        # the nearest date or collapse every mission with the same name.
        for record in rows:
            eligible = scoped[record.pk]
            if len(eligible) == 1 and sum(eligible[0] in scoped[r.pk] for r in rows) == 1:
                matches[record.pk] = eligible[0]
                continue
            same_day = [q for q in eligible if record.data is not None
                        and quest_local_date(q.questDate) == record.data]
            if len(same_day) == 1 and sum(r.data == record.data and same_day[0] in scoped[r.pk] for r in rows) == 1:
                matches[record.pk] = same_day[0]
    return matches


def _legacy_adventures(record, quest, reward):
    if (not record or not quest or quest.type != 'legacy' or quest.createdBy != 'legacy-import'
            or quest.isPublished or quest.status != 'finished' or quest.dedicatedRankId
            or quest.allowedRanks not in (None, '', '{}', '[]')
            or reward.get('dedicated_bonus_mm', 0) > 0 or reward.get('multiplier', 1) != 1):
        return None
    try:
        metadata = json.loads(quest.description)
    except (TypeError, ValueError):
        return None
    if (not isinstance(metadata, dict) or metadata.get('origin') != 'admin_validated_legacy_spreadsheet'
            or metadata.get('import_id') != record.mestre.importacao_id
            or metadata.get('source_key') != record.chave
            or metadata.get('master_number') != record.mestre.numero):
        return None
    mm = record.valor_mm
    return mm // 100 if type(mm) is int and mm > 0 and mm % 100 == 0 else None


def _public_history_text(value, limit):
    if not isinstance(value, str):
        return ''
    # Public evidence is prose, not a dump of bot identities or character keys.
    value = re.sub(r'<@!?\d+>|\b\d{15,22}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b'
                   r'|\bc(?=[a-z0-9]{23,31}\b)(?=[a-z0-9]*\d)[a-z0-9]{23,31}\b',
                   '[identidade omitida]', value[:limit], flags=re.I)
    return value.strip()


def _discord_source(value):
    if not isinstance(value, str) or len(value) > 500 or re.search(r'\s|[\\<>"\x00-\x1f]', value):
        return ''
    try:
        url = urlsplit(value)
        valid = (url.scheme == 'https' and url.hostname in ('discord.com', 'discordapp.com',
                 'ptb.discord.com', 'canary.discord.com') and url.port in (None, 443)
                 and not url.username and not url.password and not url.query and not url.fragment
                 and re.fullmatch(r'/channels/\d{15,22}/\d{15,22}/\d{15,22}', url.path))
    except ValueError:
        return ''
    return value if valid else ''


def _review_details(review):
    evidence = review.evidence if review and isinstance(review.evidence, dict) else {}
    reward = evidence.get('reward_context')
    reward = reward if isinstance(reward, dict) else {}
    context = {key: value for key, value in reward.items()
               if key in ('base_adventures', 'base_mm', 'dedicated_bonus_mm', 'final_mm')
               and type(value) is int and value >= 0}
    multiplier = reward.get('multiplier')
    if type(multiplier) in (int, float) and 0 < multiplier <= 100 and math.isfinite(multiplier):
        context['multiplier'] = multiplier
    for key in ('reason', 'source'):
        context[key] = _public_history_text(reward.get(key), 800)
    context['reason'] = {
        'weekend_double': 'Fim de semana em dobro',
        'historical_report': 'Relato historico',
    }.get(context['reason'], context['reason'])
    context['source'] = {
        'discord_report_and_po_confirmation': 'Relato do Discord e conferencia administrativa',
        'staff_confirmation': 'Conferencia administrativa',
    }.get(context['source'], context['source'])
    details = evidence.get('mission_details')
    details = details if isinstance(details, dict) else {}
    participants = details.get('participants')
    names = []
    for participant in participants[:100] if isinstance(participants, list) else []:
        name = _public_history_text(participant, 150)
        if name and '[identidade omitida]' not in name and any(c.isalpha() for c in name) and name not in names:
            names.append(name)
    return context, {'summary': _public_history_text(details.get('summary'), 12000),
                     'participants': names, 'source_url': _discord_source(details.get('source_url'))}


def _history_row(record, quest, review):
    native = bool(quest and quest.type != 'legacy' and quest.createdBy != 'legacy-import')
    reward, details = _review_details(review)
    adventures = adventure_amount(quest, review) if quest else review.adventures if review else None
    source = 'Revisão administrativa' if review and review.adventures is not None else ''
    if adventures is None:
        adventures = _legacy_adventures(record, quest, reward)
        if adventures is not None:
            source = 'Planilha validada: 100 MM por aventura'
    elif not source:
        source = 'Quantidade registrada no bot' if quest.rewardAventurasOverride is not None else 'Duração registrada no bot'
    mm = review.master_mm if review and review.master_mm is not None else reward.get('final_mm')
    mm_source = 'Revisão administrativa' if mm is not None else ''
    if mm is None and record:
        mm, mm_source = record.valor_mm, 'Planilha legada'
    day = quest_local_date(quest.questDate) if quest else None
    if record and (not quest or quest.type == 'legacy'):
        day = record.data
    finished_day = quest_local_date(quest.endDate) if native and quest.endDate else day
    return {'title': quest.name if quest else record.titulo,
            'date': day,
            'completed_date': finished_day,
            'session_key': ('bot', quest.guildId, quest.pk) if native else (
                'spreadsheet', record.mestre.importacao_id, record.chave) if record else ('legacy', quest.pk),
            'entry_origin': 'system' if native else 'manual',
            'entry_origin_label': 'Sistêmica · bot' if native else 'Manual · planilha' if record else 'Manual · legado',
            'has_spreadsheet_source': bool(record),
            'completed': quest.status == 'finished' if native else bool(record),
            'open_table': bool(native and quest.isPublished and quest.channelId
                               and quest.type.strip().casefold() not in ('privada', 'private', 'particular')),
            'adventures': adventures, 'adventures_source': source, 'master_mm': mm, 'mm_source': mm_source,
            'reward_context': reward, 'details': details,
            'has_details': bool(details['summary'] or details['participants'] or details['source_url']),
            'status': 'Concluída (planilha)' if not quest or quest.type == 'legacy' else quest.status}


def mission_history(identity):
    records = list(identity.registros.filter(tipo='adventure').order_by('-data', '-pk'))
    names = {identity.nome, identity.rotulo_original, _master_name(identity.nome), f'F{identity.numero:02d}'}
    discord = identity.discord_id or getattr(getattr(identity.user, 'profile', None), 'discord_user_id', None)
    if discord:
        names.update({discord, f'<@{discord}>', f'<@!{discord}>'})
    linked_ids = {row.bot_quest_id for row in records if row.bot_quest_id}
    scope = Q(pk__in=linked_ids) | Q(questMaster__in=names)
    review_scope = Q(legacy_master=identity) | Q(legacy_record_id__in=[r.pk for r in records]) | Q(quest_id__in=linked_ids)
    if discord:
        review_scope |= Q(master_discord_id=discord)
    reviews = list(TbRevisaoMissaoBot.objects.filter(review_scope))
    reviewed = {row.quest_id: row for row in reviews}
    scope |= Q(pk__in=reviewed)
    quests, unavailable, guild = {}, False, None
    fields = ('id', 'guildId', 'questMaster', 'name', 'questDate', 'status', 'type',
              'rewardAventurasOverride', 'timeEvents', 'description', 'createdBy', 'isPublished',
              'allowedRanks', 'dedicatedRankId', 'channelId', 'endDate')
    try:
        source_links = TbRegistroMestreLegado.objects.filter(mestre__importacao_id=identity.importacao_id).exclude(bot_quest_id='').values('bot_quest_id')
        guilds = set(BotQuest.objects.filter(pk__in=source_links).values_list('guildId', flat=True).distinct()[:2])
        guilds.update(row.guild_id for row in reviews)
        if len(guilds) == 1:
            guild = next(iter(guilds))
            scope &= Q(guildId=guild)
        else:
            scope &= Q(pk__in=linked_ids | set(reviewed))
        quests = {row.pk: row for row in BotQuest.objects.filter(scope).only(*fields).order_by('pk')[:2000]}
        for review in TbRevisaoMissaoBot.objects.filter(quest_id__in=quests):
            reviewed[review.quest_id] = review
        # A reviewed duplicate may have a completely different title from its canonical session.
        canonical = {r.canonical_id: r for r in reviewed.values() if r.decision == 'duplicate' and r.canonical_id}
        for quest in BotQuest.objects.filter(pk__in=set(canonical) - set(quests)).only(*fields)[:2000]:
            review = canonical[quest.pk]
            source = quests.get(review.quest_id)
            if quest.guildId == review.guild_id and (quest.questMaster in names
                    or source and (_owner(source.questMaster) or source.questMaster) == (_owner(quest.questMaster) or quest.questMaster)):
                quests[quest.pk] = quest
        for review in TbRevisaoMissaoBot.objects.filter(quest_id__in=canonical):
            reviewed[review.quest_id] = review
    except DatabaseError:
        unavailable = True
    record_reviews = {r.legacy_record_id: r for r in reviewed.values() if r.legacy_record_id}
    excluded_records = {r.legacy_record_id for r in reviewed.values() if r.legacy_record_id and _excluded(r)}
    matches = _history_matches(records, quests, reviewed, names=names, guild_id=guild)
    result, seen = [], set()
    for record in records:
        review = record_reviews.get(record.pk) or reviewed.get(record.bot_quest_id)
        if record.pk in excluded_records or _excluded(review) or _excluded(reviewed.get(record.bot_quest_id)):
            if record.bot_quest_id:
                seen.add(record.bot_quest_id)
            continue
        if record.bot_quest_id in seen:
            continue
        quest = quests.get(review.quest_id) if record.pk in record_reviews else quests.get(record.bot_quest_id)
        if record.pk in matches:
            quest = matches[record.pk]
            review = reviewed.get(quest.pk)
        elif quest:
            review = reviewed.get(quest.pk) or review
        if _excluded(review):
            continue
        if quest:
            if quest.pk in seen:
                if record.bot_quest_id:
                    seen.add(record.bot_quest_id)
                continue
            seen.add(quest.pk)
        if record.bot_quest_id:
            seen.add(record.bot_quest_id)
        result.append(_history_row(record, quest, review))
    for quest in quests.values():
        if quest.pk in seen or _excluded(reviewed.get(quest.pk)):
            continue
        result.append(_history_row(None, quest, reviewed.get(quest.pk)))
    result.sort(key=lambda row: row['date'].isoformat() if row['date'] else '', reverse=True)
    labels = {'finished':'Concluída', 'idle':'A iniciar', 'running':'Em andamento',
              'paused':'Pausada', 'frozen':'Suspensa', 'cancelled':'Cancelada', 'canceled':'Cancelada'}
    for row in result:
        row['status'] = labels.get(row['status'], row['status'])
    return result, unavailable


def portfolio(request, number):
    from .master_portfolio import portfolio_context
    identity = identities().filter(numero=number).order_by('-pk').first()
    if identity is None:
        raise Http404
    data = card(identity)
    history, unavailable = mission_history(identity)
    origin = request.GET.get('origem', '')
    origin = origin if origin in ('manual', 'system') else ''
    if origin:
        history = [row for row in history if row['entry_origin'] == origin]
    page = Paginator(history, 25).get_page(request.GET.get('pagina'))
    public_profile = (getattr(identity.user, 'participacao', None) if data['user'] else None)
    works = portfolio_context(data['user'], public_profile, public=True) if data['user'] else {'portfolio_cards': []}
    return render(request, 'home/pages/master_roster_portfolio.html', {
        **{key: value for key, value in data.items() if key != 'user'}, **works,
        'master_user': data['user'], 'missions_page': page, 'bot_unavailable': unavailable,
        'history_origin': origin,
        'mission_page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1),
        'mission_count': len(history), 'known_adventures': sum(r['adventures'] for r in history if r['adventures'] is not None),
        'unknown_adventures': sum(r['adventures'] is None for r in history),
        'page_title': f'F{identity.numero:02d} - {identity.nome}'})
