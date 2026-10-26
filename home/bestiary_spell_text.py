"""Present explicit spell references without guessing spells from prose."""
import re

from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def decorate_spell_text(feature, source):
    refs = source.get('spell_refs') or []
    aliases, spells = {}, {}
    for ref in refs:
        if not isinstance(ref, dict) or ref.get('resolved') is False:
            continue
        slug = ref.get('slug')
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            continue
        name = ref.get('name') or ref.get('name_en') or slug
        spells[slug] = {'nome': name, 'slug': slug}
        for alias in (ref.get('name'), ref.get('name_en')):
            if isinstance(alias, str) and alias.strip():
                aliases[alias.casefold()] = slug
    if not aliases:
        return feature
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(
        re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)) + r')(?!\w)', re.I)
    text = feature.get('texto') or ''
    pieces, used, previous = [], set(), 0
    for match in pattern.finditer(text):
        slug = aliases.get(match.group().casefold())
        if slug is None:
            continue
        pieces.append(str(escape(text[previous:match.start()])))
        pieces.append(str(format_html(
            '<a class="bonfire-card-trigger be-spell-trigger" '
            'href="/magias/listas/?magia={}" data-table="tbMagia" data-args="{}" '
            'aria-haspopup="dialog">{}</a>', slug, slug, match.group())))
        used.add(slug)
        previous = match.end()
    pieces.append(str(escape(text[previous:])))
    # Only generated anchors and escaped source text cross this safe boundary.
    feature['spell_text_html'] = format_html('<p>{}</p>', mark_safe(
        ''.join(pieces).replace('\n\n', '</p><p>').replace('\n', '<br>')))
    missing = [value for slug, value in spells.items() if slug not in used]
    if missing:
        feature['spell_extra_rows'] = [{'label': 'Magias referenciadas', 'spells': missing}]
    return feature
