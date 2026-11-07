"""Auditable legacy imports and Discord identity claims, without username guessing."""
import re
import unicodedata
from datetime import date, datetime, time, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (BotQuest, MestreOuroDireito, MestreOuroRevisao, TbAventuraMestre,
                     TbImportacaoMestre, TbMestreLegado, TbPerfilMestre,
                     TbRegistroMestreLegado, TbTransacaoMestre, UserProfile)


def normalized(value):
    text = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def require_admin(actor):
    if not (actor and actor.is_authenticated and actor.is_active and actor.is_superuser):
        raise PermissionDenied


def _number(value):
    found = re.match(r'^foguei?i?r[ae]\s*0*(\d+)\b', normalized(value))
    return int(found[1]) if found else None


def _master_name(value):
    return re.sub(r'^mestr[ea]\s+', '', normalized(value))


def _owner(value):
    value = str(value or '').strip()
    mention = re.fullmatch(r'<@!?(\d{15,22})>', value)
    return mention[1] if mention else value if re.fullmatch(r'\d{15,22}', value) else None


def quest_local_date(value):
    """Prisma DateTime is UTC in a timestamp-without-time-zone column."""
    if not isinstance(value, datetime):
        return None
    if timezone.is_naive(value):
        value = value.replace(tzinfo=datetime_timezone.utc)
    zone = ZoneInfo(getattr(settings, 'MASTER_LEGACY_TIME_ZONE', 'America/Sao_Paulo'))
    return value.astimezone(zone).date()


@transaction.atomic
def import_archive(plan, source, *, actor=None):
    """One immutable baseline per source. Changed snapshots need reconciliation."""
    if actor is not None:
        require_admin(actor)
    if (plan.get('schema') != 1 or not re.fullmatch(r'[a-f0-9]{64}', plan.get('source_sha256', ''))
            or not isinstance(source, str) or not 1 <= len(source) <= 160):
        raise ValidationError('Arquivo de importacao invalido.')
    get_user_model().objects.select_for_update().filter(pk=getattr(actor, 'pk', None)).exists()
    archive = TbImportacaoMestre.objects.select_for_update().filter(fonte=source).first()
    if archive:
        if archive.checksum != plan['source_sha256']:
            raise ValidationError('Esta fonte ja foi importada. Concilie a nova versao sem somar novamente.')
        return archive, False
    same_file = TbImportacaoMestre.objects.filter(checksum=plan['source_sha256']).first()
    if same_file:
        return same_file, False
    archive = TbImportacaoMestre.objects.create(
        fonte=source, checksum=plan['source_sha256'], dados=plan, criado_por=actor)
    masters = {}
    for row in plan['masters']:
        number = row['number']
        if type(number) is not int or number < 1 or number in masters:
            raise ValidationError('Numero de Fogueira duplicado ou invalido.')
        for name in ('balance_mm', 'table_count', 'event_coins'):
            if type(row[name]) is not int or row[name] < 0:
                raise ValidationError('Saldo ou contagem invalida.')
        masters[number] = TbMestreLegado.objects.create(
            importacao=archive, numero=number, nome=row['name'], rotulo_original=row['label'],
            saldo_mm=row['balance_mm'], mesas_declaradas=row['table_count'], moedas_evento=row['event_coins'])
    for row in plan['entries']:
        if row['master_number'] not in masters or row['kind'] not in ('adventure', 'purchase'):
            raise ValidationError('Registro sem mestre ou tipo reconhecido.')
        amount = row['amount_mm']
        if type(amount) is not int or (amount < 0 if row['kind'] == 'adventure' else amount > 0):
            raise ValidationError('Valor de registro invalido.')
        TbRegistroMestreLegado.objects.create(
            mestre=masters[row['master_number']], chave=row['key'], tipo=row['kind'], titulo=row['title'],
            data=date.fromisoformat(row['date']) if row.get('date') else None,
            valor_mm=amount, original=row)
    return archive, True


def _wallet(identity, user, *, mode='empty', expected_balance=None, expected_events=None):
    """Import once; never derive event coins a second time from historic income."""
    if identity.carteira_importada_em:
        return
    if mode == 'defer':
        identity.conciliacao = 'Vinculo de cadastro confirmado; conciliacao de moedas adiada, sem alterar saldos.'
        identity.save(update_fields=['conciliacao'])
        return
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
    balance, events = int(profile.moedas_mestragem or 0), int(profile.moedas_evento or 0)
    occupied = balance or events or profile.mm_ganhas_total or TbTransacaoMestre.objects.filter(mestre=user).exists()
    if mode == 'empty' and occupied:
        identity.conciliacao = 'Carteira existente: revisar sobreposicao antes de importar saldo.'
        identity.save(update_fields=['conciliacao'])
        return
    if mode not in ('empty', 'add', 'replace'):
        raise ValidationError('Modo de conciliacao invalido.')
    if mode != 'empty' and (type(expected_balance) is not int or type(expected_events) is not int
                            or balance != expected_balance or events != expected_events):
        raise ValidationError('A carteira mudou. Confira os saldos novamente.')
    records = list(identity.registros.select_for_update().order_by('data', 'pk'))
    running = 0
    for record in records:
        label = normalized(record.titulo)
        kind = ('aventura' if record.tipo == 'adventure' else 'mensalidade' if 'mensalidade' in label
                else 'assinatura' if label == 'mestre ouro' else 'resgate')
        running += record.valor_mm
        receipt = TbTransacaoMestre.objects.create(
            mestre=user, tipo=kind, descricao=f'[Legado F{identity.numero:02d}] {record.titulo}'[:255],
            valor_mm=record.valor_mm, saldo_mm=running)
        if record.data:
            timestamp = timezone.make_aware(datetime.combine(record.data, time(12)))
            TbTransacaoMestre.objects.filter(pk=receipt.pk).update(criado_em=timestamp)
            receipt.criado_em = timestamp
        record.transacao = receipt
        if record.tipo == 'adventure':
            record.aventura = TbAventuraMestre.objects.create(
                mestre=user, nome=record.titulo[:200], data=record.data, recompensa_mm=record.valor_mm,
                observacao=f'Importado da Fogueira {identity.numero}; registro {record.pk}')
        record.save(update_fields=['transacao', 'aventura'])
    target = identity.saldo_mm + (balance if mode == 'add' else 0)
    target_events = identity.moedas_evento + (events if mode == 'add' else 0)
    delta = target - balance - running
    TbTransacaoMestre.objects.create(
        mestre=user, tipo='ajuste', descricao=f'Conciliacao de saldo legado F{identity.numero:02d} ({mode})',
        valor_mm=delta, saldo_mm=target)
    profile.moedas_mestragem, profile.moedas_evento = target, target_events
    income = sum(max(0, row.valor_mm) for row in records)
    source_row = next(row for row in identity.importacao.dados['masters'] if row['number'] == identity.numero)
    declared_income = source_row.get('calculations', {}).get('income')
    if type(declared_income) is int and declared_income >= 0:
        income = max(income, declared_income)
    profile.mm_ganhas_total = (int(profile.mm_ganhas_total or 0) + income if mode == 'add'
                              else max(int(profile.mm_ganhas_total or 0), income))
    profile.save(update_fields=['moedas_mestragem', 'moedas_evento', 'mm_ganhas_total'])
    purchases = [row.transacao for row in records
                 if row.transacao.tipo == 'assinatura' and row.valor_mm <= -5000]
    if len(purchases) == 1:
        MestreOuroDireito.objects.get_or_create(user=user, defaults={
            'primeira_compra': purchases[0], 'adquirido_em': purchases[0].criado_em})
    elif any(row.transacao.tipo in ('assinatura', 'mensalidade') for row in records):
        MestreOuroRevisao.objects.get_or_create(user=user, defaults={'motivo': 'historico_importado_requer_conciliacao'})
    identity.carteira_importada_em = timezone.now()
    identity.conciliacao = ''
    identity.save(update_fields=['carteira_importada_em', 'conciliacao'])


def _bind(identity, user, *, actor=None, wallet_mode='empty', expected_balance=None, expected_events=None):
    from .master_registration import number_limit
    if not 1 <= identity.numero <= number_limit():
        raise ValidationError('Fogueira fora do cadastro vigente. Nenhuma permissao ou moeda foi concedida.')
    if not user.is_active or (identity.user_id and identity.user_id != user.pk):
        raise ValidationError('Identidade ja atribuida a outra conta ou conta inativa.')
    identity.user = user
    identity.vinculado_em = identity.vinculado_em or timezone.now()
    fields = ['user', 'vinculado_em']
    if actor is not None:
        identity.vinculado_por = actor
        fields.append('vinculado_por')
    identity.save(update_fields=fields)
    participation, _ = TbPerfilMestre.objects.get_or_create(user=user)
    # A suspension/refusal is an explicit moderation decision, not an absent grant.
    if participation.status_mestre not in ('suspenso', 'recusado'):
        participation.status_mestre = 'aprovado'
        if participation.modo == 'jogador':
            participation.modo = 'ambos'
        participation.save(update_fields=['status_mestre', 'modo', 'atualizado_em'])
    _wallet(identity, user, mode=wallet_mode, expected_balance=expected_balance, expected_events=expected_events)
    return identity


@transaction.atomic
def bind_master(identity_id, user_id, *, actor, wallet_mode='empty', expected_balance=None, expected_events=None):
    require_admin(actor)
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    identity = TbMestreLegado.objects.select_for_update().get(pk=identity_id)
    return _bind(identity, user, actor=actor, wallet_mode=wallet_mode,
                 expected_balance=expected_balance, expected_events=expected_events)


@transaction.atomic
def confirm_discord_masters(archive_id, checksum, confirmations, *, actor):
    """Reserve PO-confirmed Discord identities; claim only verified site accounts."""
    require_admin(actor)
    if (type(archive_id) is not int or not isinstance(checksum, str)
            or not isinstance(confirmations, list) or not 1 <= len(confirmations) <= 100):
        raise ValidationError('Informe a importacao, checksum e de 1 a 100 confirmacoes.')
    numbers, discord_ids = set(), set()
    for row in confirmations:
        if (not isinstance(row, dict) or set(row) != {'number', 'discord_id'}
                or type(row['number']) is not int or row['number'] < 1
                or not isinstance(row['discord_id'], str) or _owner(row['discord_id']) != row['discord_id']
                or row['number'] in numbers or row['discord_id'] in discord_ids):
            raise ValidationError('Confirmacoes invalidas ou repetidas; IDs devem ser texto numerico.')
        numbers.add(row['number'])
        discord_ids.add(row['discord_id'])
    # Follow the account -> identity lock order used by OAuth and manual binding.
    users = list(get_user_model().objects.select_for_update().filter(
        profile__discord_user_id__in=discord_ids).select_related('profile').order_by('pk'))
    accounts = {}
    for user in users:
        accounts.setdefault(user.profile.discord_user_id, []).append(user)
    archive = TbImportacaoMestre.objects.get(pk=archive_id)
    if archive.checksum != checksum:
        raise ValidationError('A fonte importada nao corresponde ao checksum confirmado.')
    masters = list(archive.mestres.select_for_update().order_by('pk'))
    by_number = {row.numero: row for row in masters}
    result = []
    for confirmation in confirmations:
        number, discord_id = confirmation['number'], confirmation['discord_id']
        master = by_number.get(number)
        if not master:
            raise ValidationError(f'Fogueira {number} nao existe nesta importacao.')
        if master.discord_id and master.discord_id != discord_id:
            raise ValidationError(f'Fogueira {number} ja tem outro Discord; reatribuicao recusada.')
        if any(row.pk != master.pk and row.discord_id == discord_id for row in masters):
            raise ValidationError(f'Discord da Fogueira {number} ja reservado em outra Fogueira.')
        candidates = accounts.get(discord_id, [])
        if len(candidates) > 1:
            raise ValidationError(f'Discord da Fogueira {number} aparece em mais de uma conta.')
        user = candidates[0] if candidates else None
        if (master.user_id and (not user or master.user_id != user.pk)
                or user and any(row.pk != master.pk and row.user_id == user.pk for row in masters)):
            raise ValidationError(f'Conta da Fogueira {number} conflita com vinculo existente.')
        evidence = dict(master.evidencia or {})
        if evidence.get('manual_confirmation', {}).get('discord_id') != discord_id:
            evidence['manual_confirmation'] = {'discord_id': discord_id, 'actor_id': actor.pk,
                'confirmed_at': timezone.now().isoformat(), 'source': 'superuser_confirmation'}
        master.discord_id, master.evidencia = discord_id, evidence
        master.save(update_fields=['discord_id', 'evidencia'])
        if user and user.is_active:
            _bind(master, user, actor=actor)
        result.append({'number': number, 'discord_id': discord_id, 'user_id': master.user_id,
                       'status': 'linked' if master.user_id else 'reserved',
                       'wallet_imported': bool(master.carteira_importada_em),
                       'reconciliation': master.conciliacao})
    return {'import_id': archive.pk, 'confirmed': len(result), 'masters': result}


@transaction.atomic
def claim_discord_masters(user, discord_id):
    """Call only after verified OAuth; names and user-entered text never claim funds."""
    if not _owner(discord_id) or not UserProfile.objects.filter(user=user, discord_user_id=discord_id).exists():
        return 0
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    count = 0
    for identity in TbMestreLegado.objects.select_for_update().filter(discord_id=discord_id):
        if identity.user_id not in (None, user.pk):
            continue
        # Identity and access must not depend on a successful financial import.
        _bind(identity, user, wallet_mode='defer')
        try:
            with transaction.atomic():
                _wallet(identity, user)
        except (ValidationError, DatabaseError):
            identity.conciliacao = 'Vinculo confirmado; importacao da carteira pendente de conciliacao.'
            identity.save(update_fields=['conciliacao'])
        count += 1
    from .master_mission_review import claim_review_rewards
    claim_review_rewards(user, discord_id)
    return count


@transaction.atomic
def discover_bot_links(archive_id, *, guild_id=None):
    """Inspect all relevant stored publications, not a sampled/partial author list."""
    archive = TbImportacaoMestre.objects.get(pk=archive_id)
    masters = list(archive.mestres.all())
    by_number = {row.numero: row for row in masters}
    by_name = {}
    for master in masters:
        by_name.setdefault(_master_name(master.nome), []).append(master)
    query = BotQuest.objects.filter(Q(isPublished=True) | Q(status__in=['running', 'paused', 'frozen', 'finished']))
    if guild_id is not None:
        if not _owner(guild_id):
            raise ValidationError('ID do servidor Discord invalido.')
        query = query.filter(guildId=guild_id)
    elif len(list(query.values_list('guildId', flat=True).distinct()[:2])) > 1:
        raise ValidationError('Mais de um servidor Discord. Informe guild_id para evitar cruzar comunidades.')
    if query.count() > 20000:
        raise ValidationError('Mais de 20000 publicacoes: divida a leitura antes de atribuir autores.')
    matches = {row.pk: [] for row in masters}
    quests = list(query.only('id', 'questMaster', 'createdBy', 'name', 'questDate'))
    by_title_date = {}
    for quest in quests:
        when = quest_local_date(quest.questDate)
        by_title_date.setdefault((normalized(quest.name), when), []).append(quest)
        number = _number(quest.questMaster)
        master = by_number.get(number) if number else None
        if master is None and number is None:
            names = by_name.get(_master_name(quest.questMaster), [])
            master = names[0] if len(names) == 1 else None
        if master:
            matches[master.pk].append(quest)
    coverage, record_links = {}, []
    for master in masters:
        records = list(master.registros.filter(tipo='adventure'))
        matched = 0
        for record in records:
            candidates = by_title_date.get((normalized(record.titulo), record.data), []) if record.data else []
            if len(candidates) == 1:
                quest = candidates[0]
                # A named master on an old row must not contradict the source identity.
                named_number = _number(quest.questMaster)
                named_master = _master_name(quest.questMaster)
                if (named_number and named_number != master.numero
                        or not named_number and not _owner(quest.questMaster)
                        and named_master != _master_name(master.nome)):
                    continue
                matched += 1
                if quest not in matches[master.pk]:
                    matches[master.pk].append(quest)
                record_links.append((master.pk, record.pk, quest.pk))
        coverage[master.pk] = {'adventures': len(records), 'matched': matched}
        coverage[master.pk]['quarantined_adventures'] = sum(
            warning.get('quarantine', {}).get('master_number') == master.numero
            and warning.get('quarantine', {}).get('kind') == 'adventure'
            for warning in archive.dados.get('warnings', []))
    claimed_quests = {}
    for master_id, _, quest_id in record_links:
        claimed_quests.setdefault(quest_id, set()).add(master_id)
    ambiguous_quests = {key for key, owners in claimed_quests.items() if len(owners) > 1}
    for master_id, _, quest_id in record_links:
        if quest_id in ambiguous_quests:
            coverage[master_id]['matched'] -= 1
    for master_id in matches:
        matches[master_id] = [quest for quest in matches[master_id] if quest.pk not in ambiguous_quests]
    # Match bind/claim lock order (account, identity, wallet), including batch scans.
    authors = {_owner(q.createdBy) for rows in matches.values() for q in rows} - {None}
    list(get_user_model().objects.select_for_update().filter(
        profile__discord_user_id__in=authors).order_by('pk'))
    masters = list(archive.mestres.select_for_update().order_by('pk'))
    for _, record_id, quest_id in record_links:
        if quest_id not in ambiguous_quests:
            TbRegistroMestreLegado.objects.filter(pk=record_id).update(bot_quest_id=quest_id)
    linked = ambiguous = confirmed = 0
    for master in masters:
        selected = matches[master.pk]
        owners = {_owner(row.createdBy) for row in selected}
        if len(owners) == 1 and None not in owners:
            owner = next(iter(owners))
            selected = list({row.pk: row for row in selected + [q for q in quests
                             if _owner(q.questMaster) == owner]}.values())
            owners = {_owner(row.createdBy) for row in selected}
        conflicting_master = any(_owner(q.questMaster) and _owner(q.questMaster) != _owner(q.createdBy)
                                 for q in selected)
        complete = (coverage[master.pk]['adventures'] == coverage[master.pk]['matched']
                    and not coverage[master.pk]['quarantined_adventures'])
        proven = bool(selected) and complete and not conflicting_master and None not in owners and len(owners) == 1
        evidence = {'publications': len(selected), **coverage[master.pk],
                    'authors': sorted(owner for owner in owners if owner),
                    'unknown_authors': sum(_owner(row.createdBy) is None for row in selected),
                    'master_author_conflict': conflicting_master,
                    'checked_at': timezone.now().isoformat(), 'source': 'rpg_quests.createdBy',
                    'status': 'unique' if proven else 'conflict' if selected else 'not_found'}
        manual = (master.evidencia or {}).get('manual_confirmation')
        if manual and manual.get('discord_id') == master.discord_id:
            evidence['manual_confirmation'] = manual
        master.evidencia = evidence
        if 'manual_confirmation' in evidence:
            # Missing legacy quests and staff assistance cannot revoke a PO decision.
            confirmed += 1
        elif proven and (not master.discord_id or master.discord_id in owners):
            master.discord_id = next(iter(owners))
            linked += 1
        else:
            ambiguous += int(bool(selected))
            # Never leave a previous automatic claim live after contradictory evidence.
            master.discord_id = ''
        master.save(update_fields=['evidencia', 'discord_id'])
        if master.discord_id:
            profile = UserProfile.objects.select_related('user').filter(discord_user_id=master.discord_id).first()
            if profile:
                claim_discord_masters(profile.user, master.discord_id)
    return {'masters': len(masters), 'unique_authors': linked, 'manual_confirmations': confirmed,
            'ambiguous': ambiguous,
            'publications_checked': query.count()}


def market_identity_context(user):
    from django.db import DatabaseError
    try:
        with transaction.atomic():
            return {'identidades_mestre': list(TbMestreLegado.objects.filter(user_id=user.pk))}
    except DatabaseError:
        # Optional during a rolling deployment; do not break existing redemptions.
        return {'identidades_mestre': []}
