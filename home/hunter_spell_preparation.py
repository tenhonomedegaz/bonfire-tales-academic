"""Prepare pinned Hunter spells without deleting acquired spells or fixed grants."""
from django.db import transaction
from django.db.models import Q
from .models import TbPersonagem, TbPersonagemCacador, TbPersonagemMagia
from .versioned_classes import resolved_classes
from .versioned_spells import spell_catalog


def panel(profile, sheet):
    from .views import _magias_preparadas_info
    person = profile.personagem_classe.id_personagem
    info = _magias_preparadas_info(person, sheet,
        classe_id=profile.personagem_classe.id_classe_id, ruleset=profile.ruleset)
    if info is not None:
        from .hunter_spells import granted_spells
        catalog = spell_catalog(profile.ruleset)
        fixed = {catalog[row.id_magia_id].slug for row in person.magias.filter(sempre_preparada=True)
                 if row.id_magia_id in catalog}
        fixed.update(grant['slug'] for grant in granted_spells(person, profile.ruleset))
        for group in info['grupos']:
            group['magias'] = [m for m in group['magias'] if m['slug'] not in fixed]
    return info


@transaction.atomic
def save_spells(*, character_id, owner_id, selected, expected_version):
    from .character_engine import derive
    person = TbPersonagem.objects.select_for_update().get(
        pk=character_id, dono_id=owner_id, arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related(
        'ruleset', 'personagem_classe').get(personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue antes de preparar magias.')
    info = panel(profile, derive(person, ruleset=profile.ruleset))
    if info is None:
        raise ValueError('A revisão não possui preparo de magias disponível.')
    selected = list(selected)
    allowed = {m['slug'] for group in info['grupos'] for m in group['magias']}
    if (len(selected) != len(set(selected)) or not set(selected) <= allowed
            or (info['limite'] is not None and len(selected) > info['limite'])):
        raise ValueError('Seleção de magias inválida ou acima do limite da revisão.')
    catalog = spell_catalog(profile.ruleset)
    by_slug = {spell.slug: spell for spell in catalog.values()}
    chosen_ids = {by_slug[slug].pk for slug in selected}
    pc = resolved_classes(profile.ruleset, [profile.personagem_classe])[0]
    origin = Q(origem__iexact=pc.id_classe.nome)
    if person.classes.count() == 1:
        origin |= Q(origem__isnull=True) | Q(origem='')
    rows = list(person.magias.select_for_update().filter(
        origin, nivel__gte=1, sempre_preparada=False))
    seen = set()
    for row in rows:
        if row.id_magia_id in seen:
            raise ValueError('Há magias duplicadas nesta origem; regularize antes de preparar.')
        seen.add(row.id_magia_id)
    changed = False
    for row in rows:
        prepared = row.id_magia_id in chosen_ids
        if row.preparada != prepared:
            row.preparada = prepared
            row.save(update_fields=['preparada'])
            changed = True
    for spell_id in chosen_ids - seen:
        spell = catalog[spell_id]
        TbPersonagemMagia.objects.create(id_personagem=person, id_magia_id=spell_id,
            nivel=spell.nivel, nome=spell.nome, preparada=True, origem=pc.id_classe.nome)
        changed = True
    if changed:
        profile.version += 1
        profile.save(update_fields=['version'])
    return profile
