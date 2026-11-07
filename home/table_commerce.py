"""Deterministic offer values in BRL. No network, provider or MM conversion."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError

CENT = Decimal('0.01')
REGULATION_VERSION = 'vitrine-2026-10-v1'


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite(): raise ValueError
        return result.quantize(CENT, rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError('Informe um valor monetário válido.')


def validate_offer(data):
    def get(key, default=None):
        return data.get(key, default) if isinstance(data, dict) else getattr(data, key, default)
    price = money(get('preco'))
    sessions, courtesy = get('sessoes'), get('cortesias')
    if not 0 < price <= Decimal('999999.99'):
        raise ValidationError('Defina um preço positivo e válido para a mesa paga.')
    if not isinstance(sessions,int) or not 1 <= sessions <= 52 or not isinstance(courtesy,int) or not 0 <= courtesy <= 12:
        raise ValidationError('Use entre 1 e 52 sessões contratadas e até 12 cortesias.')
    if sessions + courtesy > 1 and get('formato') == 'oneshot':
        raise ValidationError('Uma oferta com várias sessões deve usar missão múltipla ou campanha, não sessão única.')
    if get('cobranca') not in ('hora','sessao','missao','campanha','pacote','outro') or get('preco_unidade') not in ('pessoa','grupo'):
        raise ValidationError('Informe o modelo e a unidade de cobrança.')
    if not str(get('inclusoes','')).strip() or not str(get('condicoes','')).strip():
        raise ValidationError('Explique o que está incluído e as condições da oferta paga.')
    if get('cobranca') == 'pacote':
        if sessions < 2 or money(get('preco_avulso')) <= 0:
            raise ValidationError('Pacotes exigem pelo menos duas sessões e o preço avulso por sessão.')
        if price > money(get('preco_avulso')) * sessions:
            raise ValidationError('O total do pacote não pode superar a soma das sessões avulsas informadas.')
    return True


def offer_summary(table):
    if table.modalidade != 'paga':
        return dict(paid=False, total=Decimal('0.00'), label='Mesa gratuita')
    validate_offer(table)
    amount = money(table.preco)
    if table.cobranca == 'sessao': amount *= table.sessoes
    if table.cobranca == 'hora': amount *= Decimal(table.duracao_minutos) / 60 * table.sessoes
    return dict(paid=True, total=money(amount), reference=money(table.preco),
        unit=table.get_preco_unidade_display(), model=table.get_cobranca_display(),
        sessions=table.sessoes, courtesy=table.cortesias,
        demonstration=table.preco_demonstrativo, regulation=table.regulamento_versao,
        commission=Decimal('0.00'))


def package_settlement(total, sessions, standalone, completed, reason='proporcional'):
    """Supplied 190/4/60 rule; courtesy sessions never enter these counts."""
    total, standalone = money(total), money(standalone)
    if not isinstance(sessions,int) or sessions < 1 or not isinstance(completed,int) or not 0 <= completed <= sessions or total < 0 or standalone <= 0:
        raise ValidationError('Quantidade de sessões ou valores inválidos para o recálculo.')
    if reason not in ('proporcional','desistencia_jogador','falha_mestre'):
        raise ValidationError('Motivo de recálculo inválido.')
    earned = min(total, money(standalone * completed)) if reason == 'desistencia_jogador' else money(total * completed / sessions)
    return dict(earned=earned, refund=total-earned, total=total)


def session_allocations(total, sessions):
    """Last session absorbs cent rounding; the ledger always sums exactly."""
    total = money(total)
    if not isinstance(sessions,int) or sessions < 1 or total < 0:
        raise ValidationError('Distribuição de sessões inválida.')
    amount = (total / sessions).quantize(CENT, rounding='ROUND_DOWN')
    return [amount]*(sessions-1) + [total-amount*(sessions-1)]
