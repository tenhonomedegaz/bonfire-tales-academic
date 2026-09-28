"""Extract a reviewable ranger draft without mutating live game content.

This is source evidence, not an executable ruleset or a historical rules version.
"""
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.utils.text import slugify


def checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def _body(heading):
    nodes = []
    for node in heading.next_siblings:
        if getattr(node, 'name', None) in ('h2', 'h3', 'h4', 'h5'):
            break
        nodes.append(str(node))
    return BeautifulSoup(''.join(nodes), 'html.parser').get_text(' ', strip=True)


def _section(heading):
    """Keep subordinate rules, but never absorb another Order's spoiler."""
    nodes = []
    rank = int(heading.name[1])
    for node in heading.next_siblings:
        name = getattr(node, 'name', None)
        if name in ('h2', 'h3', 'h4', 'h5') and int(name[1]) <= rank:
            break
        nodes.append(str(node))
    section = BeautifulSoup(''.join(nodes), 'html.parser')
    for spoiler in section.select('.spoiler-container'):
        spoiler.decompose()
    return section.get_text(' ', strip=True)


def extract_reference(path):
    raw = Path(path).read_bytes()
    document = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    article = document.select_one('.user-css-vignette')
    if article is None:
        raise ValueError('Reference has no article content.')
    progression = []
    table = article.find('table')
    if table is None:
        raise ValueError('Reference has no progression table.')
    for row in table.select('tr')[1:]:
        cells = [cell.get_text(' ', strip=True) for cell in row.find_all('td')]
        if len(cells) != 11:
            raise ValueError('Unexpected progression columns.')
        progression.append({
            'level': int(re.search(r'\d+', cells[0])[0]),
            'proficiency': int(cells[1]), 'features': cells[2],
            'prepared_spells': int(cells[3]),
            'favored_enemies': int(cells[4]) if cells[4].isdigit() else 0,
            'hunter_die': cells[5],
            'slots': [int(c) if c.isdigit() else 0 for c in cells[6:]],
        })
    if [r['level'] for r in progression] != list(range(1, 21)):
        raise ValueError('Expected exactly levels 1 through 20.')
    entries = []
    for index, heading in enumerate(article.select('h2,h3,h4,h5')):
        title = heading.get_text(' ', strip=True)
        level = re.match(r'Nível (\d+):\s*(.+)', title)
        # An order lives inside its own spoiler; class features live in the article.
        container = heading.find_parent(class_='spoiler-content')
        owner_heading = container.find('h2') if container else None
        owner = owner_heading.get_text(' ', strip=True) if owner_heading else ''
        parent_section = heading.find_previous(['h2', 'h3', 'h4'])
        parent_title = parent_section.get_text(' ', strip=True) if parent_section else ''
        entry = {'id': '%03d-%s' % (index, slugify(title)), 'heading': heading.name,
                 'title': title, 'owner': owner, 'parent': parent_title,
                 'level': int(level[1]) if level else None,
                 'name': level[2] if level else title, 'text': _body(heading),
                 'section_text': _section(heading)}
        entry['checksum'] = checksum(entry)
        entries.append(entry)
    orders = sorted({e['owner'] for e in entries if e['owner'].startswith('Ordem ')})
    if len(orders) != 8:
        raise ValueError('Expected eight orders, found %d.' % len(orders))
    payload = {'schema': 1, 'state': 'source-draft',
               'source_file': Path(path).name,
               'source_sha256': hashlib.sha256(raw).hexdigest(),
               'progression': progression, 'orders': orders, 'entries': entries,
               'article_text': article.get_text(' ', strip=True),
               'activation_ready': False}
    payload['checksum'] = checksum(payload)
    return payload


def compare_fixture(reference, fixture):
    """Compare names/levels only; never infer identity equivalence from similar text."""
    rows = json.loads(Path(fixture).read_text(encoding='utf-8'))
    classes = [row for row in rows if row['model'] == 'home.tbclasse'
               and row['fields'].get('slug') == 'cacador']
    if len(classes) != 1:
        raise ValueError('Expected one ranger in the baseline fixture.')
    class_id = classes[0]['pk']
    subclasses = {row['pk']: row['fields']['nome'] for row in rows
                  if row['model'] == 'home.tbsubclasse'
                  and row['fields'].get('id_classe') == class_id}
    baseline = [row for row in rows if row['model'] == 'home.tbclassehabilidade'
                and row['fields'].get('id_classe') == class_id]
    comparisons = []
    for row in baseline:
        fields = row['fields']
        owner = subclasses.get(fields.get('id_subclasse'), '')
        matches = [e['id'] for e in reference['entries']
                   if e['heading'] == 'h3' and e['name'] == fields['nome']
                   and e['level'] == fields['niveladquirido'] and e['owner'] == owner]
        comparisons.append({'legacy_id': row['pk'], 'name': fields['nome'],
                            'level': fields['niveladquirido'], 'owner': owner,
                            'baseline_payload': fields, 'baseline_checksum': checksum(fields),
                            'candidate_ids': matches,
                            'action': 'review-effects' if matches else 'manual-mapping-required'})
    return {'baseline_file': Path(fixture).name,
            'baseline_sha256': hashlib.sha256(Path(fixture).read_bytes()).hexdigest(),
            'warning': 'Fixture comparison only; not a snapshot of the live database.',
            'features': comparisons}


def write_draft(path, payload):
    """Exclusive creation prevents accidental replacement of an earlier review artifact."""
    with Path(path).open('x', encoding='utf-8') as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write('\n')
