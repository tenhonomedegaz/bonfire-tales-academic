"""Stage explicitly reviewed bestiary images without changing catalog records."""

import hashlib
from io import BytesIO
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_EXTENSIONS = {'.webp', '.png', '.jpg', '.jpeg'}


class ImageStageError(ValueError):
    pass


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def stage_images(preview, selection, output_dir, fetch_blob):
    """Fetch selected immutable blobs after explicit usage review; never writes DB."""
    by_slug = {row['slug']: row for row in preview.get('records', [])}
    items = selection.get('items')
    if not isinstance(items, list) or not items or len(items) > 20:
        raise ImageStageError('Seleção deve conter entre 1 e 20 imagens.')
    seen = set()
    approved = []
    for item in items:
        slug = item.get('slug') if isinstance(item, dict) else None
        if not isinstance(slug, str) or slug in seen:
            raise ImageStageError('Slug inválido ou repetido.')
        seen.add(slug)
        row = by_slug.get(slug)
        if not row or row.get('status') != 'candidate_exact' or len(row.get('candidates', [])) != 1:
            raise ImageStageError(f'Candidato não exato: {slug}')
        candidate = row['candidates'][0]
        sha = candidate.get('sha')
        path = candidate.get('path')
        if (not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha) or
                item.get('source_sha') != sha or
                not isinstance(path, str) or Path(path).suffix.lower() not in IMAGE_EXTENSIONS):
            raise ImageStageError(f'Origem alterada ou inválida: {slug}')
        for field in ('usage_basis', 'reviewer', 'attribution'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ImageStageError(f'{field} não revisado: {slug}')
        approved.append((row, candidate, item))

    output_dir = Path(output_dir)
    staged = []
    for row, candidate, item in approved:
        sha = candidate['sha']
        suffix = Path(candidate['path']).suffix.lower()
        original = output_dir / f'{sha}{suffix}'
        thumb = output_dir / f'{sha}-thumb.webp'
        if original.exists():
            data = original.read_bytes()
        else:
            data = fetch_blob(sha)
        if not isinstance(data, bytes) or len(data) > MAX_IMAGE_BYTES or git_blob_sha(data) != sha:
            raise ImageStageError(f'Checksum ou tamanho inválido: {row["slug"]}')
        try:
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ImageStageError(f'Imagem grande demais: {row["slug"]}')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.thumbnail((320, 320))
                output = BytesIO()
                image.convert('RGB').save(output, format='WEBP', quality=85)
                thumbnail = output.getvalue()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageStageError(f'Imagem inválida: {row["slug"]}: {exc}') from exc
        if thumb.exists() and thumb.read_bytes() != thumbnail:
            raise ImageStageError(f'Miniatura existente divergente: {row["slug"]}')
        output_dir.mkdir(parents=True, exist_ok=True)
        if not original.exists():
            original.write_bytes(data)
        if not thumb.exists():
            thumb.write_bytes(thumbnail)
        staged.append({'pk': row['pk'], 'slug': row['slug'], 'source_path': candidate['path'],
                       'source_blob_sha': sha, 'original': str(original),
                       'original_sha256': hashlib.sha256(data).hexdigest(),
                       'thumbnail': str(thumb),
                       'thumbnail_sha256': hashlib.sha256(thumbnail).hexdigest(),
                       'usage_basis': item['usage_basis'].strip(),
                       'reviewer': item['reviewer'].strip(),
                       'attribution': item['attribution'].strip()})
    return staged
