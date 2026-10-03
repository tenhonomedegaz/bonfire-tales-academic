"""URLs de imagens usadas em atributos de imagem e CSS de perfis."""

from django import template

from home.editorial_links import safe_editorial_image


register = template.Library()


@register.filter
def safe_profile_image(value):
    return safe_editorial_image(value)
