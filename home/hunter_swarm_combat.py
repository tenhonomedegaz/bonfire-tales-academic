"""Swarm combat preview; conditions and turn availability are declared by the user."""

COMMANDS = (
    ('weakening', 'Enxame Enfraquecedor'),
    ('push', 'Força dos Muitos'),
    ('step', 'Passo da Colônia'),
    ('subjugate', 'Subjugação da Horda'),
)


def evaluate(prepared, combat, *, commands=(), hit=False, own_turn=False,
             command_used=False, marked=False, damage=0, barrier_used=False,
             barrier_ability='int', intelligence=10, wisdom=10):
    damage = int(damage)
    if damage < 0:
        raise ValueError('O dano total não pode ser negativo.')
    if barrier_ability not in ('int', 'wis'):
        raise ValueError('Escolha INT ou SAB para Barreira Viva.')
    commands = list(commands)
    if len(commands) != len(set(commands)) or not set(commands) <= dict(COMMANDS).keys():
        raise ValueError('Escolha comandos diferentes e válidos.')
    level = prepared['level']
    swarm = prepared['order'] == 'ordem-do-enxame' and level >= 3
    limit = (2 if level >= 10 and marked else 1) if swarm else 0
    if len(commands) > limit:
        raise ValueError('Quantidade de comandos excede o limite para este alvo e nível.')
    available = swarm and hit and own_turn and not command_used
    if commands and not available:
        raise ValueError('Comande após acertar no seu turno, uma vez por turno.')
    die = '1' + prepared['progression']['hunter_die']
    effects = []
    for command in commands:
        if command == 'weakening':
            text = ('Desvantagem no próximo ataque antes do início do seu próximo turno; '
                    'se acertar, reduza o dano em ' + die + '.')
        elif command == 'push':
            text = f'Resistência de Força CD {combat["spell_dc"]}; na falha, empurre 15 pés.'
        elif command == 'step':
            text = 'Mova-se horizontalmente até 5 pés para espaço desocupado, sem Ataques de Oportunidade.'
        else:
            text = (f'Resistência de Força CD {combat["spell_dc"]}; na falha, deslocamento pela metade '
                    'e sem Ataques de Oportunidade até o início do seu próximo turno.')
        effects.append({'id': command, 'name': dict(COMMANDS)[command], 'text': text})
    score = int(intelligence if barrier_ability == 'int' else wisdom)
    if not 1 <= score <= 30:
        raise ValueError('O atributo da Barreira deve estar entre 1 e 30.')
    threshold = level + max(1, (score - 10) // 2) if swarm and level >= 6 else None
    blocked = threshold is not None and not barrier_used and 0 < damage <= threshold
    return dict(enabled=swarm, command_limit=limit, command_available=available,
                extra_damage=die if commands else '', effects=effects,
                barrier_threshold=threshold, barrier_blocked=blocked,
                damage_taken=0 if blocked else damage)
