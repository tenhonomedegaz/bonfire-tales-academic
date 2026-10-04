"""Template bridge for cosmetic media packages; access is checked server side."""

from django import template

from home.cosmetic_packages import get_package


register = template.Library()


@register.simple_tag
def cosmetic_package(tipo, value, user):
  """Return a validated package for the selected profile slot, if eligible."""
  return get_package(user, tipo, value, 'perfil')
