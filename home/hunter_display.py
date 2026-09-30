"""Presentation for the published Hunter, without changing frozen rules text."""
import hashlib
import html
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


RULES = Path(__file__).parent / 'rules'
EXPLANATORY_FEATURE_IDS = frozenset({
    '076-nivel-3-ordem-do-cacador',
    '129-nivel-6-habilidade-da-ordem',
    '149-nivel-10-habilidade-da-ordem',
    '171-nivel-14-habilidade-da-ordem',
    '192-nivel-18-habilidade-da-ordem',
})


def _inline(node):
    if isinstance(node, NavigableString):
        return html.escape(re.sub(r'\s+', ' ', str(node)), quote=False)
    name = node.name
    if name == 'br':
        return '\n'
    content = ''.join(_inline(child) for child in node.children).strip()
    if name in ('strong', 'b'):
        return f'**{content}**'
    if name in ('em', 'i'):
        return f'*{content}*'
    # World Anvil anchors may contain script-generated destinations. The
    # selector on this page is the authoritative way to open an Order card.
    return content


def _blocks(section, order_names):
    result = []
    for node in section.children:
        if isinstance(node, NavigableString):
            text = _inline(node).strip()
            if text:
                result.append(text)
            continue
        name = node.name
        if name in ('p', 'em', 'blockquote'):
            text = _inline(node).strip()
            if text:
                result.append(text)
        elif name in ('h4', 'h5', 'h6'):
            result.append('#### ' + _inline(node).strip())
        elif name in ('ul', 'ol'):
            for index, item in enumerate(node.find_all('li', recursive=False), 1):
                result.append(('- ' if name == 'ul' else f'{index}. ') + _inline(item).strip())
        elif name == 'hr':
            continue
        elif name == 'table':
            rows = [[_inline(cell).strip() for cell in row.find_all(['th', 'td'], recursive=False)]
                    for row in node.find_all('tr')]
            if rows and all(len(row) == len(rows[0]) for row in rows):
                result.append('| ' + ' | '.join(rows[0]) + ' |\n| ' +
                              ' | '.join(['---'] * len(rows[0])) + ' |\n' +
                              '\n'.join('| ' + ' | '.join(row) + ' |' for row in rows[1:]))
        elif name == 'a':
            title = node.get_text(' ', strip=True)
            if title in order_names:
                from django.utils.text import slugify
                link = f'- [{html.escape(title)}](?subclasse={slugify(title)}-rework)'
                if result and result[-1].startswith('- ['):
                    result[-1] += '\n' + link
                else:
                    result.append(link)
        else:
            nested = _blocks(node, order_names)
            if nested:
                result.append(nested)
    return '\n\n'.join(result)


def build_display(reference_path):
    """Extract formatting only when the source exactly matches frozen text."""
    from .ranger_reference import extract_reference

    source = Path(reference_path)
    rules = json.loads((RULES / 'hunter_content.json').read_text(encoding='utf-8'))
    reference = extract_reference(source)
    if reference['source_sha256'] != rules['source_sha256']:
        raise ValueError('Hunter source checksum changed')
    article = BeautifulSoup(source.read_text(encoding='utf-8'), 'html.parser').select_one('.user-css-vignette')
    headings = article.select('h2,h3,h4,h5')
    output = {}
    for feature in rules['features']:
        heading = next((head for index, head in enumerate(headings)
                        if feature['id'].startswith(f'{index:03d}-')), None)
        if heading is None:
            raise ValueError('Hunter heading missing: ' + feature['id'])
        rank = int(heading.name[1])
        nodes = []
        for node in heading.next_siblings:
            name = getattr(node, 'name', None)
            if name in ('h2', 'h3', 'h4', 'h5') and int(name[1]) <= rank:
                break
            nodes.append(str(node))
        section = BeautifulSoup(''.join(nodes), 'html.parser')
        for spoiler in section.select('.spoiler-container'):
            spoiler.decompose()
        if section.get_text(' ', strip=True) != feature['text']:
            raise ValueError('Hunter frozen text differs from source: ' + feature['id'])
        output[hashlib.sha256(feature['text'].encode('utf-8')).hexdigest()] = _blocks(
            section, set(rules['orders']))
    if len(output) != len(rules['features']):
        raise ValueError('Hunter feature descriptions are not unique')
    return {'schema': 1, 'source_sha256': rules['source_sha256'], 'features': output}


def display_descriptions():
    rules = json.loads((RULES / 'hunter_content.json').read_text(encoding='utf-8'))
    display = json.loads((RULES / 'hunter_display.json').read_text(encoding='utf-8'))
    if display['schema'] != 1 or display['source_sha256'] != rules['source_sha256']:
        raise ValueError('Hunter display source does not match published content')
    return display['features']


def explanatory_cards(existing_descriptions):
    """Source-identified explanatory cards; never added to the game catalog."""
    from types import SimpleNamespace

    rules = json.loads((RULES / 'hunter_content.json').read_text(encoding='utf-8'))
    existing = {hashlib.sha256((text or '').encode('utf-8')).hexdigest()
                for text in existing_descriptions}
    cards = []
    for feature in rules['features']:
        if feature['id'] not in EXPLANATORY_FEATURE_IDS:
            continue
        digest = hashlib.sha256(feature['text'].encode('utf-8')).hexdigest()
        if digest in existing:
            continue
        cards.append(SimpleNamespace(
            id_habilidade='hunter-display-' + feature['id'],
            nome=feature['name'], descricao=feature['text'],
            niveladquirido=feature['level'], id_subclasse=None,
            id_subclasse_id=None, table_only=False,
        ))
    return cards
