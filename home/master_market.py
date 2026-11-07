"""Bounded MM redemptions, with the existing ledger as the delivery receipt."""

import re
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (TbPersonagem, TbPersonagemAventura, TbRecompensaMestre,
                     TbReiDaColina, TbTransacao, TbTransacaoMestre, UserProfile)


TOKEN_SALT = 'home.master-market.redemption'


class RedemptionError(ValueError):
    pass


def quantity_limit(reward):
    if reward.tipo != 'normal':
        return 1
    return max(1, min(1000, int(getattr(settings, 'MASTER_MARKET_MAX_QUANTITY', 100))))


def parse_quantity(raw, limit=1000):
    raw = '1' if raw is None else str(raw)
    if not re.fullmatch(r'[0-9]{1,4}', raw):
        raise RedemptionError('quantidade')
    quantity = int(raw)
    if not 1 <= quantity <= limit:
        raise RedemptionError('quantidade')
    return quantity


def redemption_token(user_id, reward_id, unit_price, effect='manual'):
    return signing.dumps([user_id, reward_id, unit_price, uuid4().hex, effect], salt=TOKEN_SALT)


def _operation(token, user_id, reward_id):
    if not token:
        return None
    try:
        data = signing.loads(token, salt=TOKEN_SALT)
        owner, reward, price, operation = data[:4]
        effect = data[4] if len(data) == 5 else None
        if len(data) not in {4, 5}:
            raise ValueError
        if (owner != user_id or reward != reward_id or type(price) is not int
                or not re.fullmatch(r'[0-9a-f]{32}', operation)):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError):
        raise RedemptionError('operacao') from None
    return price, operation, effect


def _destination(raw):
    if raw in (None, ''):
        return None
    if not re.fullmatch(r'[0-9]{1,10}', str(raw)) or int(raw) < 1:
        raise RedemptionError('sem_personagem')
    return int(raw)


def _deliver_adventures(character, quantity, events, receipt):
    from .character_engine import (
        braseiros_por_aventura, nivel_por_aventuras, ouro_de_progressao, rank_por_nivel,
    )

    base = int(character.aventuras or 0)
    gold = (ouro_de_progressao(base + quantity) - ouro_de_progressao(base)) * 100
    levels = [nivel_por_aventuras(base + k) for k in range(quantity)]
    embers = sum(braseiros_por_aventura(level) for level in levels) if events else 0
    # A redemption is not a played mission and must not manufacture mission achievements.
    TbPersonagem.objects.filter(pk=character.pk).update(
        aventuras=F('aventuras') + quantity, carteira_pc=F('carteira_pc') + gold,
        braseiros=F('braseiros') + embers, atualizado_em=timezone.now())
    character.refresh_from_db(fields=['aventuras', 'carteira_pc', 'braseiros'])
    details = {
        'contrato': 'aventura_recompensa:v1', 'usar_moedas_evento': events,
        'moedas_evento_gastas': quantity if events else 0,
        'aventuras_antes': base, 'aventuras_depois': character.aventuras,
        'ouro_pago_pc': gold, 'braseiros_pago': embers, 'niveis_recompensa': levels,
        'ranks_recompensa': [rank_por_nivel(level) for level in levels],
        'nivel_personagem_no_resgate': int(character.nivel or 1),
        'criterio_braseiros': 'rank_progressao_antes_de_cada_aventura',
        'transacao_mm_id': receipt.pk,
    }
    adventure = TbPersonagemAventura.objects.create(
        id_personagem=character, origem='mercado_mestre',
        nome_aventura='Resgate do Mercado de Mestre', qtd_aventuras=quantity,
        ouro_pago_pc=gold, braseiros_pago=embers, nivel_no_lancamento=character.nivel or 1,
        criado_por_id=receipt.mestre_id, detalhes_json=details)
    gold_receipt = TbTransacao.objects.create(
        id_personagem=character, tipo='aventura', descricao='Resgate do Mercado de Mestre',
        valor_pc=gold, saldo_pc=character.carteira_pc,
        detalhes_json={'origem': 'mercado_mestre', 'transacao_mm_id': receipt.pk,
                       'adventure_ledger_id': adventure.pk})
    return {**details, 'aventura_ledger_id': adventure.pk, 'ouro_transacao_id': gold_receipt.pk}


def redeem_reward(user, reward_id, raw_quantity=None, token=None, *,
                  character_id=None, use_event_coins=None):
    """Tokens deduplicate new forms; older POST clients may omit token/quantity."""
    quantity = parse_quantity(raw_quantity)
    try:
        reward_id = int(reward_id)
    except (TypeError, ValueError):
        raise RedemptionError('invalido') from None
    operation = _operation(token, user.pk, reward_id)
    destination = _destination(character_id)
    if use_event_coins not in (None, '', 'on'):
        raise RedemptionError('operacao')
    events = use_event_coins == 'on'
    marker = '[mm:%s:%s:%s]' % (operation[1], reward_id, quantity) if operation else ''

    with transaction.atomic():
        # Serialize this wallet before checking either receipts or available MM.
        profile = UserProfile.objects.select_for_update().get(user_id=user.pk)
        if operation:
            receipt = TbTransacaoMestre.objects.filter(mestre=user, operacao=operation[1]).first()
            if receipt:
                if (receipt.recompensa_id != reward_id or receipt.quantidade != quantity
                        or receipt.personagem_id != destination
                        or receipt.detalhes_json.get('usar_moedas_evento', False) != events):
                    raise RedemptionError('operacao')
                return ('rei' if receipt.tipo == 'leilao' else
                        'entregue' if receipt.personagem_id else 'resgatado')
            legacy = TbTransacaoMestre.objects.filter(
                mestre=user, operacao__isnull=True,
                descricao__contains='[mm:%s:' % operation[1]).first()
            if legacy:
                if destination or events:
                    raise RedemptionError('conciliacao')
                if not legacy.descricao.endswith(marker):
                    raise RedemptionError('operacao')
                return 'rei' if legacy.tipo == 'leilao' else 'resgatado'

        reward = TbRecompensaMestre.objects.filter(pk=reward_id, ativo=True).first()
        if reward is None or reward.tipo not in {'normal', 'leilao', 'assinatura'}:
            raise RedemptionError('invalido')
        quantity = parse_quantity(raw_quantity, quantity_limit(reward))
        if reward.tipo == 'assinatura':
            return 'slots'

        auction = None
        if reward.tipo == 'leilao':
            # Lock in stable order, including when the singleton needs initialization.
            offers = list(TbRecompensaMestre.objects.select_for_update().filter(
                tipo='leilao').order_by('pk'))
            reward = next((offer for offer in offers if offer.pk == reward_id and offer.ativo), None)
            if reward is None:
                raise RedemptionError('invalido')
            auction = TbReiDaColina.objects.select_for_update().order_by('pk').first()
            if auction is None:
                auction = TbReiDaColina.objects.create()
            if auction.holder_id == user.pk:
                raise RedemptionError('ja_rei')
            unit_price = auction.preco_atual
        else:
            reward = TbRecompensaMestre.objects.select_for_update().get(pk=reward_id)
            if not reward.ativo or reward.tipo != 'normal':
                raise RedemptionError('invalido')
            unit_price = reward.preco_mm

        if unit_price < 0:
            raise RedemptionError('invalido')
        if operation and operation[0] != unit_price:
            raise RedemptionError('preco')
        effect = reward.efeito
        if effect not in {'manual', 'aventura_recompensa'} or (effect != 'manual' and auction):
            raise RedemptionError('invalido')
        if operation and operation[2] != effect and not (operation[2] is None and effect == 'manual'):
            raise RedemptionError('contrato')
        character = None
        if effect == 'aventura_recompensa':
            if operation is None:
                raise RedemptionError('operacao')
            character = TbPersonagem.objects.select_for_update().filter(
                pk=destination, dono=user, arquivado=False).first()
            if character is None:
                raise RedemptionError('sem_personagem')
        elif destination or events:
            raise RedemptionError('contrato')
        total = unit_price * quantity
        # Conditional debit also protects against writers that do not lock wallets.
        updated = UserProfile.objects.filter(pk=profile.pk, moedas_mestragem__gte=total).update(
            moedas_mestragem=F('moedas_mestragem') - total)
        if not updated:
            raise RedemptionError('saldo')
        if events:
            updated = UserProfile.objects.filter(pk=profile.pk, moedas_evento__gte=quantity).update(
                moedas_evento=F('moedas_evento') - quantity)
            if not updated:
                raise RedemptionError('sem_evento')
        profile.refresh_from_db(fields=['moedas_mestragem'])
        suffix = ' (%d MM/un.; total %d MM)%s' % (unit_price, total, ' ' + marker if marker else '')
        prefix = 'Resgate: %d x ' % quantity if auction is None else 'Rei da Colina: %d x ' % quantity
        description = prefix + reward.nome[:255 - len(prefix) - len(suffix)] + suffix
        receipt = TbTransacaoMestre.objects.create(
            mestre=user, tipo='leilao' if auction else 'resgate', descricao=description,
            valor_mm=-total, saldo_mm=profile.moedas_mestragem,
            operacao=operation[1] if operation else None, recompensa=reward,
            personagem=character, quantidade=quantity,
            detalhes_json={'efeito': effect, 'preco_unitario_mm': unit_price,
                           'usar_moedas_evento': events})
        if character:
            receipt.detalhes_json.update(_deliver_adventures(character, quantity, events, receipt))
            receipt.save(update_fields=['detalhes_json'])
        if auction:
            auction.holder = user
            auction.preco_atual = unit_price + 100
            auction.desde = timezone.now()
            auction.save(update_fields=['holder', 'preco_atual', 'desde'])
    return 'rei' if auction else 'entregue' if character else 'resgatado'
