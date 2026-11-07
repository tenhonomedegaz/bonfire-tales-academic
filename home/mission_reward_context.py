"""Validated historical facts; describing a reward never issues a payment."""
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


def reward_context(value, *, adventures, master_mm):
    if not isinstance(value, dict) or set(value) - {
            'base_adventures', 'multiplier', 'reason', 'base_mm',
            'dedicated_bonus_mm', 'final_mm', 'source'}:
        raise ValidationError('Contexto de recompensa invalido.')
    base, multiplier = value.get('base_adventures'), value.get('multiplier')
    if (type(base) is not int or not 0 <= base <= 100
            or type(multiplier) is not int or not 1 <= multiplier <= 10
            or type(adventures) is not int or base * multiplier != adventures):
        raise ValidationError('Aventuras-base e multiplicador divergem da recompensa final.')
    base_mm, bonus, total = (value.get(key) for key in ('base_mm', 'dedicated_bonus_mm', 'final_mm'))
    if (any(type(number) is not int or not 0 <= number <= 100000 for number in (base_mm, bonus, total))
            or base_mm != adventures * 100 or base_mm + bonus != total or total != master_mm):
        raise ValidationError('Moedas-base, bonus e total divergem do registro aprovado.')
    for key in ('reason', 'source'):
        if not isinstance(value.get(key), str) or not 1 <= len(value[key].strip()) <= 160:
            raise ValidationError('Informe motivo e fonte da recompensa.')
    return {**value, 'reason': value['reason'].strip(), 'source': value['source'].strip()}


def mission_details(value, *, guild_id):
    if not isinstance(value, dict) or set(value) - {'summary', 'participants', 'source_url'}:
        raise ValidationError('Detalhes da missao invalidos.')
    summary, participants, url = value.get('summary', ''), value.get('participants', []), value.get('source_url', '')
    if not isinstance(summary, str) or len(summary) > 12000:
        raise ValidationError('Resumo deve ter ate 12000 caracteres.')
    if (not isinstance(participants, list) or len(participants) > 30
            or any(not isinstance(name, str) or not 1 <= len(name.strip()) <= 150 for name in participants)):
        raise ValidationError('Informe ate 30 nomes de participantes, com ate 150 caracteres.')
    if not isinstance(url, str) or len(url) > 300:
        raise ValidationError('Referencia da missao invalida.')
    if url:
        try:
            parsed = urlsplit(url)
        except ValueError:
            raise ValidationError('Referencia da missao invalida.') from None
        parts = parsed.path.strip('/').split('/')
        if (parsed.scheme != 'https' or parsed.netloc != 'discord.com' or parsed.query or parsed.fragment
                or len(parts) != 4 or parts[:2] != ['channels', str(guild_id)]
                or not all(15 <= len(part) <= 22 and part.isascii() and part.isdigit() for part in parts[1:])):
            raise ValidationError('Referencia deve apontar para mensagem do Discord neste servidor.')
    return {'summary': summary.strip(), 'participants': list(dict.fromkeys(name.strip() for name in participants)),
            'source_url': url}
