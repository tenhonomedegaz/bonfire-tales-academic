"""Read-only organization prose and image projections; original data is untouched."""

import json
import re

from .editorial_links import safe_editorial_image


MARKDOWN_IMAGE = re.compile(r'!\[([^\]]*)\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["\'][^"\']*["\'])?\s*\)')


def organization_presentation(description, image=''):
    text = description if isinstance(description, str) else ''
    for _ in range(3):
        if not text.strip().startswith('"'):
            break
        try:
            decoded = json.loads(text)
        except (ValueError, TypeError):
            break
        if not isinstance(decoded, str):
            break
        text = decoded
    image_url = safe_editorial_image(image)
    alt = ''
    body = text
    for match in MARKDOWN_IMAGE.finditer(text):
        candidate = safe_editorial_image(match.group(2).strip('<>'))
        if not candidate:
            continue
        if not image_url or image_url == candidate:
            image_url = candidate
            alt = match.group(1)
            body = (text[:match.start()] + text[match.end():]).strip()
        break
    return {'descricao': text, 'descricao_leitura': body,
            'imagem': image_url, 'imagem_alt': alt}
