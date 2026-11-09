"""Adapt pinned preparation services to the laboratory's shared choice cards."""
from .hunter_preparation import preparation
from .models import TbPersonagemCacador


def _profiles(personagem):
    return TbPersonagemCacador.objects.filter(
        personagem_classe__id_personagem=personagem).select_related(
            'ruleset', 'personagem_classe__id_classe', 'personagem_classe__id_subclasse')


def _key(profile):
    # Temporary character/profile IDs change on every rollback preview.
    return 'preparation|%s|secrets' % profile.personagem_classe.id_classe.slug


def _prepare(profile, **kwargs):
    pc = profile.personagem_classe
    return preparation(profile, allow_pending_order=(pc.nivel >= 3 and not pc.id_subclasse_id),
                       **kwargs)


def apply_preparations(personagem, build):
    incoming = build.get('escolhas') or {}
    for profile in _profiles(personagem):
        selected = incoming.get(_key(profile), profile.selected)
        result = _prepare(profile, selected=selected)
        if profile.selected != result['selected']:
            profile.selected = result['selected']
            profile.save(update_fields=['selected'])


def preparation_groups(personagem):
    groups = []
    for profile in _profiles(personagem):
        result = _prepare(profile)
        if result['level'] < 2 or (result['level'] >= 3 and not result['order']):
            continue
        automatic = [row for row in result['available'] if row['automatic']]
        selected = [row for row in result['available'] if not row['automatic']]
        groups.append({
            'key': _key(profile), 'kind': 'preparation',
            'label': 'Segredos preparados',
            'classe': profile.personagem_classe.id_classe.nome,
            'origem': ('Linha Mestra: %s' % result['master'] if result['master']
                       else 'Preparos de Caçada'),
            'optional': True,
            'limite': result['proficiency'] + len(automatic),
            'usados': len(automatic) + len(selected), 'pendentes': 0,
            'opcionais_restantes': result['proficiency'] - len(selected),
            'selecionadas': result['selected'],
            'resolvidas': [{'valor': row['id'], 'nome': row['name']}
                          for row in automatic + selected],
            'automaticas': [{'nome': row['name'], 'descricao': row['text']}
                            for row in automatic],
            'opcoes': [{'valor': row['id'], 'nome': row['name'],
                        'descricao': row['text'],
                        'meta': '%s · Grau %s · %s PS' % (
                            row['line'], row['degree'], row['cost'])}
                       for row in result['options'] if not row['automatic']],
        })
    return groups


def _expertise_state(profile, personagem):
    from .character_engine import derive
    from .hunter_expertise import choice_state
    return choice_state(profile, derive(personagem, ruleset=profile.ruleset)['pericias'])


def apply_expertise_choices(personagem, build):
    from .hunter_expertise import validate_selection
    from .models import TbPersonagemEscolha
    incoming = build.get('escolhas') or {}
    for profile in _profiles(personagem):
        key = 'expertise|%s' % profile.personagem_classe.id_classe.slug
        if key not in incoming:
            continue
        state = _expertise_state(profile, personagem)
        if state is None:
            raise ValueError('A revisao vinculada nao oferece esta especializacao.')
        added = [value for value in incoming[key] if value not in state['selected']]
        validate_selection(state, state['selected'] + added, complete=False)
        for slot, value in enumerate(added, start=len(state['selected'])):
            TbPersonagemEscolha.objects.create(id_personagem=personagem,
                origem='hunter:%s:expertise' % profile.pk, tipo='hunter-expertise',
                slot=slot, valor=value)


def expertise_groups(personagem, build):
    groups = []
    for profile in _profiles(personagem):
        state = _expertise_state(profile, personagem)
        if state is None or not state['limit']:
            continue
        key = 'expertise|%s' % profile.personagem_classe.id_classe.slug
        requested = (build.get('escolhas') or {}).get(key, [])
        fixed = set(state['selected']) - set(requested)
        groups.append({
            'key': key, 'kind': 'expertise', 'label': 'Especialização de perícias',
            'classe': profile.personagem_classe.id_classe.nome, 'origem': 'Instinto de Caçador',
            'optional': False, 'limite': state['limit'], 'usados': len(state['selected']),
            'pendentes': state['remaining'], 'selecionadas': requested,
            'resolvidas': [{'valor': row['id'], 'nome': row['nome']}
                          for row in state['options'] if row['selected']],
            'opcoes': [{'valor': row['id'], 'nome': row['nome'],
                        'descricao': '', 'meta': row['atributo']}
                       for row in state['options'] if row['id'] not in fixed],
        })
    return groups
