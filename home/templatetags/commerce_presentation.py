"""Read-only storefront media. Never resolves or grants account entitlements."""
import json
import re

from django import template
from django.templatetags.static import static

from home.cosmetic_packages import PACKAGE_ROOT, parse_package
from home.editorial_links import safe_editorial_image


register = template.Library()


@register.filter
def collaborator_icon(product_code):
    """Resolve catalog artwork only; product and checkout data stay unchanged."""
    filename = {
        'colaborador-conde-1m': 'conde-condessa.png',
        'colaborador-marques-1m': 'marques-marquesa.png',
        'colaborador-duque-1m': 'duque-duquesa.png',
        'token-missao': 'missao-especial.png',
        'token-boost': 'boost.png',
        'token-superboost': 'superboost.png',
    }.get(product_code)
    return static('icons/collaborator/' + filename) if filename else ''


@register.filter
def shop_type(kind):
    return {
        'tema': 'Tema',
        'moldura': 'Moldura',
        'efeito': 'Efeito',
        'titulo': 'Título',
        'badge': 'Insígnia',
        'banner_preset': 'Banner',
    }.get(kind, 'Cosmético')


@register.simple_tag
def shop_visual(cosmetic):
    """Return public catalog art without checking or changing entitlements.

    Only a validated static manifest or a safe badge image is used. Unknown
    items receive an illustrative type symbol, not fake art. Catalog CSS and
    client-supplied paths are never applied to the page.
    """
    kind = getattr(cosmetic, 'tipo', '')
    result = {'kind': kind, 'image': '', 'glyph': '', 'exact': False}
    if kind == 'badge':
        asset = str(getattr(cosmetic, 'asset_efetivo', '') or '').strip()
        result['image'] = safe_editorial_image(asset)
        if (not result['image'] and len(asset) <= 24 and asset.isprintable()
                and not any(char in asset for char in '/:\\<>')):
            result['glyph'] = asset
        result['exact'] = bool(result['image'] or result['glyph'])

    slug = getattr(cosmetic, 'slug', '')
    if (kind in ('tema', 'moldura', 'efeito', 'banner_preset')
            and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug or '')):
        path = PACKAGE_ROOT / (slug + '.json')
        try:
            if path.stat().st_size <= 16 * 1024:
                package = parse_package(
                    json.loads(path.read_text(encoding='utf-8')), slug, kind)
                if package:
                    for slot in ('avatar', 'banner', 'ornament'):
                        if package[slot]:
                            result['image'] = package[slot][0]['fallback']
                            result['exact'] = True
                            break
        except (OSError, ValueError):
            pass
    return result
