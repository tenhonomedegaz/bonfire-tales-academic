"""Battle Familiar base block, from ref/FAMILIAR_DE_BATALHA.md.

Hunter overrides belong to hunter_companion, never to the common spell.
"""

FORMS = {'bruto': 'Bruto', 'voador': 'Voador', 'espreitador': 'Espreitador'}


def stat_block(circle, form, spell_attack=0):
    if isinstance(circle, bool) or not isinstance(circle, int) or not 2 <= circle <= 9:
        raise ValueError('Familiar de Batalha exige círculo de 2 a 9.')
    if form not in FORMS:
        raise ValueError('Escolha Bruto, Voador ou Espreitador.')
    talented = circle // 2
    attributes = [dict(name=name, score=score, modifier=(score - 10) // 2,
                       save=(score - 10) // 2 + talented)
                  for name, score in [('FOR', 16), ('DES', 16), ('CON', 12),
                                      ('INT', 8), ('SAB', 13), ('CAR', 10)]]
    return dict(circle=circle, form=form, form_label=FORMS[form],
                ac=11 + circle + (2 if form == 'bruto' else 0),
                hp_max=(30 if form == 'bruto' else 20) + 5 * (circle - 2),
                initiative=3, initiative_score=13, attributes=attributes,
                check_save_bonus=talented, multiattack=talented,
                rend_damage=f'1d8+{3 + circle}', rend_attack=spell_attack,
                damage_type='Força', reach_m=1.5, walk_m=12, swim_m=9,
                fly_m=9 if form == 'voador' else 0, hover=form == 'voador',
                flyby=form == 'voador', stalk=form == 'espreitador',
                passive_perception=11, size='Médio', alignment='Neutro',
                condition_immunities=['Enfeitiçado', 'Amedrontado'])
