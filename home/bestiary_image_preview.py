"""Read-only image candidate matching for imported bestiary creatures."""

from collections import Counter, defaultdict
from pathlib import Path


SOURCE_FOLDERS = {"MM'25": 'XMM', 'MPMM': 'MPMM', 'FTD': 'FTD',
                  'VGM': 'VGM', "PHB'24": 'XPHB'}
IMAGE_SUFFIXES = {'.webp', '.png', '.jpg', '.jpeg'}


def preview_images(source_rows, creatures, assets_by_folder):
    """Match by original name AND edition; never select or download a file."""
    by_identity = defaultdict(list)
    for row in source_rows:
        by_identity[(str(row.get('Name') or '').strip().casefold(),
                     str(row.get('Source') or '').strip())].append(row)

    files = {}
    for folder, entries in assets_by_folder.items():
        names = defaultdict(list)
        for entry in entries:
            name = entry.get('name') or ''
            if Path(name).suffix.lower() in IMAGE_SUFFIXES:
                names[Path(name).stem.casefold()].append({
                    'path': entry.get('path') or f'bestiary/{folder}/{name}',
                    'sha': entry.get('sha'), 'size': entry.get('size'),
                })
        files[folder] = names

    results = []
    for creature in creatures:
        fields = creature['fields']
        if fields.get('comunidade') or fields.get('autor') or fields.get('imagem_url'):
            continue
        original = (fields.get('statblock_json') or {}).get('name_en') or ''
        matched_sources = [(edition, row) for (name, edition), rows in by_identity.items()
                           if name == original.strip().casefold() for row in rows]
        if len(matched_sources) != 1:
            status = 'ambiguous_source' if matched_sources else 'missing_source'
            candidates = []
            edition = None
            page = None
        else:
            edition, source = matched_sources[0]
            page = source.get('Page')
            folder = SOURCE_FOLDERS.get(edition)
            candidates = files.get(folder, {}).get(original.strip().casefold(), [])
            status = ('unknown_edition' if not folder else
                      'source_unavailable' if folder not in files else
                      'candidate_exact' if len(candidates) == 1 else
                      'ambiguous_image' if candidates else 'no_exact_image')
        results.append({'pk': creature['pk'], 'slug': fields.get('slug'),
                        'name_en': original, 'edition': edition, 'page': page,
                        'status': status, 'candidates': candidates})
    return {'summary': dict(Counter(row['status'] for row in results)),
            'rights_status': 'unreviewed', 'records': results}
