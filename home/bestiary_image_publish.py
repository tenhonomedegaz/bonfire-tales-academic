"""Bind reviewed image thumbnails to unchanged official creatures."""

import hashlib
from io import BytesIO
from pathlib import Path
import re

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from .editorial_links import safe_editorial_image
from .bestiary_image_stage import MAX_IMAGE_BYTES, git_blob_sha
from .models import TbBestiario


class ImagePublicationError(ValueError):
    pass


def publication_plan(report, stage_dir):
    """Preflight every row and byte before any database or storage write."""
    stage_dir = Path(stage_dir).resolve()
    items = report.get('staged') if isinstance(report, dict) else None
    if not isinstance(items, list) or not items or len(items) > 20:
        raise ImagePublicationError('Relatório deve conter entre 1 e 20 imagens preparadas.')
    seen = set()
    seen_slugs = set()
    plan = []
    for item in items:
        if not isinstance(item, dict):
            raise ImagePublicationError('Item inválido no relatório.')
        pk, slug, sha = item.get('pk'), item.get('slug'), item.get('source_blob_sha')
        if not isinstance(pk, int) or not isinstance(slug, str) or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ImagePublicationError('Identidade ou origem inválida.')
        if pk in seen or slug in seen_slugs:
            raise ImagePublicationError('Criatura repetida.')
        seen.add(pk)
        seen_slugs.add(slug)
        if not all(isinstance(item.get(field), str) and item[field].strip()
                   for field in ('usage_basis', 'reviewer', 'attribution')):
            raise ImagePublicationError(f'Revisão de uso incompleta: {slug}')
        original = Path(item.get('original', '')).resolve()
        if not original.is_relative_to(stage_dir) or not original.is_file():
            raise ImagePublicationError(f'Origem ausente ou fora da preparação: {slug}')
        original_data = original.read_bytes()
        if (not original_data or len(original_data) > MAX_IMAGE_BYTES or
                git_blob_sha(original_data) != sha or
                hashlib.sha256(original_data).hexdigest() != item.get('original_sha256')):
            raise ImagePublicationError(f'Origem alterada: {slug}')
        thumbnail = Path(item.get('thumbnail', '')).resolve()
        if not thumbnail.is_relative_to(stage_dir) or not thumbnail.is_file():
            raise ImagePublicationError(f'Miniatura ausente ou fora da preparação: {slug}')
        data = thumbnail.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if not data or digest != item.get('thumbnail_sha256'):
            raise ImagePublicationError(f'Miniatura alterada: {slug}')
        try:
            with Image.open(BytesIO(data)) as image:
                if image.format != 'WEBP' or max(image.size) > 320:
                    raise ImagePublicationError(f'Miniatura fora do padrão: {slug}')
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImagePublicationError(f'Miniatura inválida: {slug}') from exc
        creature = TbBestiario.objects.filter(pk=pk, slug=slug, comunidade=False).first()
        if creature is None:
            raise ImagePublicationError(f'Criatura oficial não encontrada: {slug}')
        storage_name = f'bestiario/{sha}-thumb.webp'
        url = default_storage.url(storage_name)
        if not safe_editorial_image(url):
            raise ImagePublicationError(f'URL de mídia inválida: {slug}')
        if creature.imagem_url and creature.imagem_url != url:
            raise ImagePublicationError(f'Imagem existente preservada: {slug}')
        if default_storage.exists(storage_name):
            with default_storage.open(storage_name, 'rb') as handle:
                if hashlib.sha256(handle.read()).hexdigest() != digest:
                    raise ImagePublicationError(f'Arquivo de mídia divergente: {slug}')
        plan.append({'pk': pk, 'slug': slug, 'storage_name': storage_name,
                     'url': url, 'data': data, 'sha256': digest,
                     'already_linked': creature.imagem_url == url})
    return plan


def publish_images(report, stage_dir):
    """Apply an explicitly reviewed report; preserve existing and community art."""
    plan = publication_plan(report, stage_dir)
    with transaction.atomic():
        locked = list(TbBestiario.objects.select_for_update().filter(
            pk__in=[row['pk'] for row in plan]))
        current = {obj.pk: obj for obj in locked}
        for row in plan:
            obj = current.get(row['pk'])
            if obj is None or obj.slug != row['slug'] or obj.comunidade or (
                    obj.imagem_url and obj.imagem_url != row['url']):
                raise ImagePublicationError(f'Criatura alterada desde a prévia: {row["slug"]}')
        for row in plan:
            if not default_storage.exists(row['storage_name']):
                name = default_storage.save(row['storage_name'], ContentFile(row['data']))
                if name != row['storage_name']:
                    raise ImagePublicationError(f'Nome de mídia divergente: {row["slug"]}')
            obj = current[row['pk']]
            if obj.imagem_url != row['url']:
                obj.imagem_url = row['url']
                obj.save(update_fields=['imagem_url'])
    return [{key: row[key] for key in ('pk', 'slug', 'url', 'sha256', 'already_linked')}
            for row in plan]
