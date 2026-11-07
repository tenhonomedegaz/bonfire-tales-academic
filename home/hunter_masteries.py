"""Three proficient weapons and one replacement per completed long rest."""
from django.db import transaction
from .content_versions import resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY
from .versioned_items import item_catalog
from .versioned_options import VersionedOptions
from .hunter_preparation import preparation
from .models import TbItemMundano, TbPersonagem, TbPersonagemCacador, TbPersonagemEscolha


def available_options(person, ruleset):
    from .character_engine import weapon_proficiency_matchers, weapon_allowed
    from .item_mecanica import mecanica_de_tags
    from .picks import weapon_mastery_slugs, normalize_slug
    profs = weapon_proficiency_matchers(person, ruleset=ruleset)
    options = {normalize_slug(o['slug']):o for o in VersionedOptions(ruleset).data['options']
               if o['tipo']=='Maestria de Arma'}
    available = []
    for weapon in item_catalog(ruleset, 'mundane-item-catalog', TbItemMundano).values():
        if weapon.categoria != 'arma' or not weapon_allowed(profs, weapon.subcategoria,
                weapon.slug, weapon.nome,
                mecanica_de_tags(weapon.tags_json, weapon.subcategoria).get('propriedades', [])):
            continue
        for mastery in weapon_mastery_slugs(weapon):
            option = options.get(normalize_slug(mastery))
            if option is None:
                raise ValueError('Maestria ausente do catálogo congelado.')
            available.append(dict(value=weapon.slug+'|'+mastery, name=weapon.nome+' — '+option['nome']))
    return available


def state(profile):
    rules = resolve_content(profile.ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                            vocabulary_version=VOCABULARY).get('weapon_masteries')
    if not rules or preparation(profile, selected=[], allow_pending_order=True)['level'] < rules['level']:
        return None
    person = profile.personagem_classe.id_personagem
    available = available_options(person, profile.ruleset)
    selected = list(person.escolhas.filter(tipo='hunter-mastery', origem=f'hunter:{profile.pk}:mastery')
                    .order_by('slot').values_list('valor',flat=True))
    credit = person.escolhas.filter(tipo='hunter-mastery-rest', origem=f'hunter:{profile.pk}:mastery').first()
    return dict(options=available, selected=selected, count=rules['count'],
                can_replace=bool(credit and credit.valor=='1'))


@transaction.atomic
def save(*, character_id, owner_id, selected, expected_version):
    person = TbPersonagem.objects.select_for_update().get(pk=character_id,dono_id=owner_id,arquivado=False)
    profile = TbPersonagemCacador.objects.select_for_update().select_related('ruleset','personagem_classe').get(
        personagem_classe__id_personagem=person)
    if profile.version != int(expected_version):
        raise ValueError('A ficha mudou. Recarregue as Maestrias.')
    current = state(profile)
    selected = list(selected)
    if current is None or len(selected)!=current['count'] or len({v.split('|')[0] for v in selected})!=len(selected):
        raise ValueError('Escolha três armas diferentes.')
    if not set(selected)<={o['value'] for o in current['options']}:
        raise ValueError('Escolha armas proficientes e Maestrias da revisão vinculada.')
    previous = set(current['selected'])
    if set(selected)==previous:
        return
    if previous and (not current['can_replace'] or len(previous-set(selected))!=1):
        raise ValueError('O Descanso Longo permite trocar uma Maestria.')
    if previous and {v.split('|')[0] for v in previous} == {v.split('|')[0] for v in selected}:
        raise ValueError('A troca de Armas de Caçada exige outra arma.')
    origin=f'hunter:{profile.pk}:mastery'
    for slot,value in enumerate(selected):
        TbPersonagemEscolha.objects.update_or_create(id_personagem=person,tipo='hunter-mastery',
            origem=origin,slot=slot,defaults={'valor':value,'id_opcao':None})
    TbPersonagemEscolha.objects.update_or_create(id_personagem=person,tipo='hunter-mastery-rest',
        origem=origin,slot=0,defaults={'valor':'0','id_opcao':None})
    profile.version+=1
    profile.save(update_fields=['version'])


@transaction.atomic
def grant_rest(person):
    """A rest grants one replacement, never accumulates replacements."""
    TbPersonagem.objects.select_for_update().get(pk=person.pk)
    for profile in TbPersonagemCacador.objects.filter(personagem_classe__id_personagem=person):
        origin=f'hunter:{profile.pk}:mastery'
        if person.escolhas.filter(tipo='hunter-mastery',origem=origin).exists():
            TbPersonagemEscolha.objects.update_or_create(id_personagem=person,tipo='hunter-mastery-rest',
                origem=origin,slot=0,defaults={'valor':'1','id_opcao':None})
