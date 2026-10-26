"""Template bridge for cosmetic media packages; access is checked server side."""

from django import template

from home.cosmetic_packages import get_package, load_package


register = template.Library()


@register.simple_tag(name='character_rank')
def character_rank_tag(character):
  from home.ranks import character_rank
  return character_rank(character) if character else {}


@register.simple_tag
def cosmetic_package(tipo, value, user, escopo='perfil'):
  """Use the owner's entitlement, not the visitor's, in either presentation."""
  return get_package(user, tipo, value, escopo)


@register.simple_tag
def cosmetic_media_options(themes, frames, effects):
  """Serialize media only for the server-authorized sheet selector options."""
  return {kind:{item['key']:load_package(kind,item['key'],'ficha')
                for item in options if not item.get('locked')}
          for kind,options in (('tema',themes),('moldura',frames),('efeito',effects))}
