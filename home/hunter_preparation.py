"""Pinned Hunter preparation. Binding is explicit; never infer it from class slug."""
from django.db import transaction
from django.db.models import Sum
from django.utils.text import slugify

from .content_versions import resolve_content
from .hunter_rework import prepare
from .models import TbPersonagem, TbPersonagemCacador
from .versioned_classes import EVALUATOR, VOCABULARY, resolved_classes


def preparation(profile, *, selected=None, allow_pending_order=False):
    pc = resolved_classes(profile.ruleset, [profile.personagem_classe])[0]
    data = resolve_content(profile.ruleset, 'hunter-rework',
                           evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
    if pc.id_classe.slug != 'cacador':
        raise ValueError('A revisão vinculada não é de Caçador.')
    level = int(pc.nivel)
    # Resolve order by its frozen name; current catalog edits cannot reassign a line.
    order = slugify(pc.id_subclasse.nome) if level >= 3 and pc.id_subclasse else ''
    total = pc.id_personagem.classes.aggregate(total=Sum('nivel'))['total']
    return prepare(level=level, total_level=total, ability=profile.ability, order=order,
                   selected=profile.selected if selected is None else selected, data=data,
                   allow_pending_order=allow_pending_order)


@transaction.atomic
def save_preparation(*, character_id, owner_id, selected, expected_version):
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de preparar os Segredos.')
    result = preparation(profile, selected=selected)
    if profile.selected != result['selected']:
        profile.selected = result['selected']
        profile.version += 1
        profile.save(update_fields=['selected', 'version'])
    return profile
