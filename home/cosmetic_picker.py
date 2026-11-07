"""Lazy public previews over the active catalog, without granting cosmetics."""

import json
import re
from pathlib import Path
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import cosmetic_discovery
from .cosmetic_packages import load_package
from .cosmetics import (THEME_CATEGORIES, _scope_ok, cosmetic_read_context,
                        sanitize_definicao_tema, theme_category)


PRESENTATION_PATH = Path(__file__).parent / 'static/cosmetics/catalog-presentation.json'
_REGISTRY_LIMIT = 256 * 1024
_KEY = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
_THUMBNAIL = re.compile(r'cosmetics/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|webp)')
_LOCAL_IMAGE = re.compile(r'/(?:static|media)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|webp)')


def _presentation_metadata():
    """Read one bounded, approved registry, never the media manifests."""
    try:
        with PRESENTATION_PATH.open('rb') as source:
            payload = source.read(_REGISTRY_LIMIT + 1)
        if len(payload) > _REGISTRY_LIMIT:
            return {}
        data = json.loads(payload)
    except (OSError, ValueError):
        return {}
    if (not isinstance(data, dict) or type(data.get('version')) is not int or
            data['version'] != 1 or not isinstance(data.get('items'), dict)):
        return {}
    return data['items']


def _thumbnail_url(item, metadata):
    thumbnail = metadata.get('thumbnail')
    if isinstance(thumbnail, str) and _THUMBNAIL.fullmatch(thumbnail):
        return static(thumbnail)
    asset = item.get('asset_url')
    if isinstance(asset, str) and _THUMBNAIL.fullmatch(asset):
        return static(asset)
    return asset if isinstance(asset, str) and _LOCAL_IMAGE.fullmatch(asset) else ''


def picker_items(options, tipo, escopo):
    """Copy option metadata and existing locks; do not load media or ownership."""
    registry = _presentation_metadata()
    preview_path = reverse('cosmetic_picker_preview')
    items = []
    for option in options:
        item = dict(option)
        item.pop('package', None)
        metadata = registry.get(item.get('slug') or tipo + '-' + item['key'], {})
        if not isinstance(metadata, dict):
            metadata = {}
        category = item.get('categoria') or item.get('category') or metadata.get('category')
        item.update(
            locked=bool(item.get('locked') or item.get('estado') == 'bloqueado'),
            selected=bool(item.get('selected')),
            thumbnail_url=_thumbnail_url(item, metadata),
            category=category if category in THEME_CATEGORIES else theme_category(item),
            unlock_hint=item.get('unlock_hint') or item.get('requisito') or '',
            posse_origem=item.get('posse_origem') or '',
            preview_url=preview_path + '?' + urlencode({
                'tipo': tipo, 'key': item['key'], 'escopo': escopo}),
        )
        items.append(item)
    return items


@never_cache
@login_required
@require_GET
def cosmetic_picker_preview(request):
    tipo = request.GET.get('tipo', '')
    key = request.GET.get('key', '')
    escopo = request.GET.get('escopo', '')
    if (tipo not in {'tema', 'moldura', 'efeito'} or escopo not in {'perfil', 'ficha'} or
            not 1 <= len(key) <= 100 or not _KEY.fullmatch(key) or
            any(len(request.GET.getlist(name)) != 1 for name in ('tipo', 'key', 'escopo'))):
        return JsonResponse({'error': 'Invalid preview parameters.'}, status=400)
    with cosmetic_read_context():
        snapshot = cosmetic_discovery._read_snapshot(request.user)
        item = next((entry for entry in snapshot['catalog'].values()
                     if entry['tipo'] == tipo and entry['key'] == key and
                     _scope_ok(entry, escopo)), None)
        if item is None:
            return JsonResponse({'error': 'Cosmetic not found.'}, status=404)
        state, reason, links = cosmetic_discovery._availability(item, snapshot, timezone.now())
        presentation = picker_items([item], tipo, escopo)[0]
        response = JsonResponse({
            'key': key, 'tipo': tipo, 'label': item['label'],
            'description': item.get('descricao') or '',
            'locked': state not in {'disponivel', 'possuido'},
            'unlock_hint': reason,
            'acquisition': links[0] if links else {'label': '', 'url': ''},
            'package': load_package(tipo, key, escopo),
            'css_class': item.get('class') or '',
            'theme_definition': sanitize_definicao_tema(item.get('definicao')) if tipo == 'tema' else {},
            'theme_css_url': (item.get('css_url') or '') if tipo == 'tema' else '',
            'theme_category': presentation['category'],
            'thumbnail_url': presentation['thumbnail_url'],
        })
    patch_vary_headers(response, ('Cookie',))
    return response
