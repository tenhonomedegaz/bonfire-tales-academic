"""Permanent account rewards backed by real character builds, not public visibility."""

from django.contrib.auth import get_user_model
from django.db import transaction


def rank_unlock_metadata(raw):
    from .character_engine import aventuras_para_nivel
    from .conquistas import ranks_verificaveis

    if not isinstance(raw, dict):
        return {}, ''
    unlock = raw.get('desbloqueio')
    if (not isinstance(unlock, dict) or type(unlock.get('schema_version')) is not int
            or unlock.get('schema_version') != 1 or not isinstance(unlock.get('rank'), str)
            or unlock.get('metric') != 'rank_reached' or unlock.get('permanent') is not True):
        return {}, ''
    level = ranks_verificaveis(permanentes=True).get(unlock.get('rank'))
    if level is None:
        return {}, ''
    metadata = dict(unlock, min_level=min(level, 20),
                    min_adventures=aventuras_para_nivel(level))
    target = ('lvl 20 e o patamar Epic Boon' if level == 21 else f'lvl {level}')
    return metadata, f'alcance {target} com um personagem pra liberar'


def eligible_character_level(character):
    """Current persisted build and adventure tier must both support the milestone."""
    from .character_engine import nivel_por_aventuras

    rows = list(character.classes.all())
    if (not 1 <= character.nivel <= 20 or character.aventuras < 0 or not rows
            or sum(row.principal for row in rows) != 1
            or any(not 1 <= row.nivel <= 20 for row in rows)
            or sum(row.nivel for row in rows) != character.nivel):
        return 0
    adventure_level = nivel_por_aventuras(character.aventuras)
    return min(adventure_level, character.nivel if character.nivel < 20 else 21)


@transaction.atomic
def sync_rank_cosmetics(user):
    """Idempotent read-repair and signal hook; never undo staff suspensions.

    No on_commit or ownership cache: preview transactions roll grants back too.
    Previously granted rewards survive lost levels and deleted characters.
    """
    from .conquistas import conceder_conquista, ranks_verificaveis, regra_rank_valida
    from .models import TbConquista, TbPersonagem, TbUsuarioConquista, TbUsuarioCosmetico

    if not getattr(user, 'pk', None) or not getattr(user, 'is_authenticated', False):
        return 0
    rules = [rule for rule in TbConquista.objects.filter(
        ativo=True, criterio='automatico', criterio_json__metric='rank_reached',
        criterio_json__retention='permanent',
    ).prefetch_related('recompensas_extras') if regra_rank_valida(rule.criterio_json)]
    if not rules:
        return 0
    get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
    grants = {grant.conquista_id: grant for grant in TbUsuarioConquista.objects.filter(
        user=user, conquista__in=rules)}
    level, character = 0, None
    if any(rule.pk not in grants for rule in rules):
        characters = TbPersonagem.objects.filter(dono=user).prefetch_related('classes')
        proven = [(eligible_character_level(character), character) for character in characters]
        level, character = max(proven, key=lambda entry: entry[0], default=(0, None))
    owned = set(TbUsuarioCosmetico.objects.filter(user=user).values_list('cosmetico_id', flat=True))
    thresholds = ranks_verificaveis(permanentes=True)
    created = 0
    for rule in rules:
        grant = grants.get(rule.pk)
        if grant and grant.revogada_em is not None:
            continue
        if grant is None and level < thresholds[rule.criterio_json['filters']['rank']]:
            continue
        reward_ids = {reward.pk for reward in rule.recompensas_extras.all()}
        if rule.recompensa_id:
            reward_ids.add(rule.recompensa_id)
        if grant is not None and reward_ids <= owned:
            continue
        fresh = conceder_conquista(user, rule, preservar_suspensoes=True)
        owned.update(reward_ids)
        created += fresh
        if fresh:
            TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                evidencia_json={'personagem_id': character.pk, 'nivel': character.nivel,
                                'aventuras': character.aventuras,
                                'rank': rule.criterio_json['filters']['rank']},
                definicao_json=rule.criterio_json)
    return created
