"""Read-only market guides based on the current shop, without source rules or prices."""

from functools import lru_cache
from pathlib import Path


_GUIDES = Path(__file__).resolve().parent / 'data' / 'mundane-market-reference.txt'


@lru_cache(maxsize=1)
def _guide_copy():
    sections = {}
    for block in _GUIDES.read_text(encoding='utf-8').strip().split('\n\n'):
        ident, title, *paragraphs = block.splitlines()
        if ident not in ('[guide-sobre]', '[guide-economia]') or not paragraphs:
            raise ValueError('Unexpected market guide content')
        sections[ident[1:-1]] = (title, paragraphs)
    if set(sections) != {'guide-sobre', 'guide-economia'}:
        raise ValueError('Market guides are incomplete')
    return sections


def market_inventory_context(items, groups):
    """Add editorial guides; all items, prices, filters and purchase forms stay canonical."""
    category = {'value': 'guias-do-mercado', 'label': 'Guias do mercado', 'total': 2, 'a_venda': 0}
    entries = []
    for ident, (title, paragraphs) in _guide_copy().items():
        entries.append({
            'id': ident, 'name': title, 'type': 'guide', 'category': category,
            'icon': 'guide', 'paragraphs': paragraphs, 'notes': [], 'search': ' '.join(paragraphs),
        })
    return {
        'market_extra_entries': entries,
        'market_browser_groups': [*groups, category],
        'market_browser_total': len(items) + len(entries),
        'market_legacy_navigation': {},
    }
