"""Apply a temporary HP grant using the character's evaluated tag operations."""

from .character_engine import _build_ctx, derive
from .tag_engine import ParseError, evaluate_tags


def received_temporary_hp(amount, operations):
    if type(amount) is not int or amount < 0:
        raise ValueError('PV temporários recebidos devem ser um inteiro não negativo.')
    if amount == 0:
        return 0
    bonus = sum(
        max(0, int(op['value']))
        for op in operations
        if op.get('active') and op.get('op') == 'heal'
        and op.get('target') == 'pv_temporario'
        and isinstance(op.get('value'), (int, float))
        and not isinstance(op.get('value'), bool)
    )
    return amount + bonus


def grant_temporary_hp(personagem, amount, *, ruleset=None):
    """Replace a lower pool after applying grants from the canonical sheet tags."""
    operations = []
    if amount:
        sheet = derive(personagem, ruleset=ruleset)
        context = dict(_build_ctx(sheet['nivel_total'], sheet['bonus_proficiencia'],
                                  sheet['atributos']), resolve_runtime=True,
                       event='receive_temp_hp', self_hp=personagem.pv_atual,
                       self_max_hp=sheet['pv']['maximo_calculado'])
        for feature in sheet['tags_brutas']:
            try:
                operations.extend(vars(op) for op in evaluate_tags(
                    feature['tags'], context).operations)
            except ParseError:
                # A ficha já informa o erro dessa fonte; não interrompa a concessão.
                continue
    received = received_temporary_hp(amount, operations)
    personagem.pv_temporario = max(personagem.pv_temporario or 0, received)
    personagem.save(update_fields=['pv_temporario'])
    return received
