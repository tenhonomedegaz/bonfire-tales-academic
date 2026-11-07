"""Template bridge for cosmetic media packages; access is checked server side."""

from django import template
from django.urls import reverse

from home.cosmetic_packages import get_package, load_package
from home.cosmetic_picker import picker_items


register = template.Library()


@register.inclusion_tag('home/includes/cosmetic_catalog.html')
def cosmetic_catalog(options, tipo, select_id, select_name, selected_value='',
                     escopo='perfil', label='', select_class=''):
  """Public thumbnails do not grant access; keep the catalog's server-side locks."""
  items = picker_items(options, tipo, escopo)
  for item in items:
    item['selected'] = item['key'] == selected_value
  return {'items': items, 'tipo': tipo, 'select_id': select_id,
          'select_name': select_name, 'label': label, 'select_class': select_class,
          'preview_url': reverse('cosmetic_picker_preview'), 'escopo': escopo}


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
