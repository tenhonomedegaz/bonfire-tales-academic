"""Base Hunter combat rules; caller declares the target and turn conditions.

This evaluator does not mutate targets or consume actions. Order effects are
composed separately; conditional benefits must never become permanent bonuses.
"""


def evaluate(prepared, *, intelligence=10, wisdom=10, walking_speed=30,
             marked=False, favored=False, secret_affected=False,
             first_attack=False, third_attack_available=True,
             protective_ability='int', injured=False, punishment_available=True,
             enemy_hit_this_turn=False, final_hunt=False,
             first_turn=False, in_dim_light=False, using_attack_action=False):
    intelligence, wisdom, walking_speed = int(intelligence), int(wisdom), int(walking_speed)
    if not 1 <= intelligence <= 30 or not 1 <= wisdom <= 30:
        raise ValueError('Os atributos devem estar entre 1 e 30.')
    if not 0 <= walking_speed <= 1000:
        raise ValueError('Informe o deslocamento base em pés, entre 0 e 1000.')
    level, proficiency = prepared['level'], prepared['proficiency']
    exterminator = prepared['order'] == 'ordem-dos-exterminadores'
    exorcist = prepared['order'] == 'ordem-dos-exorcistas' and level >= 3
    twilight = prepared['order'] == 'ordem-do-crepusculo' and level >= 3
    twilight_extra = bool(twilight and using_attack_action and
                          (first_turn or (level >= 14 and in_dim_light)))
    if protective_ability not in ('int', 'wis'):
        raise ValueError('Escolha INT ou SAB para Contramedidas Protetivas.')
    protection = ((intelligence if protective_ability == 'int' else wisdom) - 10) // 2
    favored = favored or (exterminator and level >= 10 and marked)
    final_hunt = bool(final_hunt and exterminator and level >= 18 and marked)
    modifier = ((intelligence if prepared['ability'] == 'int' else wisdom) - 10) // 2
    domination = level == 20 and (marked or secret_affected)
    walk = walking_speed + (10 if level >= 7 else 0)
    return {
        'spell_dc': 8 + proficiency + modifier,
        'spell_attack': proficiency + modifier,
        'secret_dc': 8 + proficiency + modifier,
        'favored_damage': max(1, modifier) if favored and level >= 2 else 0,
        'mark_damage': ('2' if final_hunt else '1') + prepared['progression']['hunter_die'] if marked else '',
        'exterminator': exterminator,
        'mortuary_mark': bool(exorcist and marked),
        'mortuary_bleeding_bonus': proficiency if exorcist and marked and injured else 0,
        'effective_favored': bool(favored and level >= 2),
        'punishment_damage': '1' + prepared['progression']['hunter_die']
            if exterminator and marked and injured and punishment_available else '',
        'favored_save_bonus': protection if exterminator and level >= 6 and favored else 0,
        'damage_reduction': max(1, protection) if exterminator and level >= 6 and favored else 0,
        'executor_ac_bonus': 4 if exterminator and level >= 14 and enemy_hit_this_turn else 0,
        'execution_area_die': '1' + prepared['progression']['hunter_die']
            if exterminator and level >= 10 and marked else '',
        'final_hunt': final_hunt,
        'twilight_extra_attack': twilight_extra,
        'twilight_extra_damage': (level if first_turn else level // 2)
            if twilight_extra else 0,
        'twilight_marked_invisible': bool(twilight and marked and in_dim_light),
        'twilight_mark_blocks_special_sight': bool(twilight and marked),
        'twilight_miss_die': prepared['progression']['hunter_die']
            if twilight and level >= 10 else '',
        'twilight_shadow_step': bool(twilight and level >= 10 and in_dim_light),
        'ignore_damage_resistance': final_hunt,
        'prevents_healing': final_hunt,
        'attack_advantage': bool(domination or (marked and level >= 11 and first_attack)),
        'enemy_attack_disadvantage': bool(domination),
        'forced_check_save_advantage': bool(domination),
        'attacks': 3 if domination and third_attack_available else (2 if level >= 5 else 1),
        'third_attack_once_per_turn': bool(domination and third_attack_available),
        'physical_save_bonus': modifier if level >= 9 else 0,
        'walking_speed': walk,
        'climbing_speed': walk if level >= 7 else None,
        'swimming_speed': walk if level >= 7 else None,
        'bonus_dash': level >= 7,
        'bonus_hide': level >= 13,
        'charmed_immune': level >= 15,
        'possession_domination_immune': level >= 15,
        'frightened_save_advantage': level >= 15,
        'blindsight': 30 if level >= 17 else 0,
        'mark_during_attack': level >= 11,
    }
