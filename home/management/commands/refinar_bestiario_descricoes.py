import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.management.commands.importar_bestiario_csv import (
    CSV_PATH,
    SECOES,
    _load_spell_alignment,
    _repo_path,
    _resolve_spell_alignment,
    _slug_criatura,
    _spell_catalog,
    _split_secao,
)
from home.models import TbBestiario


PLACEHOLDER_RE = re.compile(
    r'^(?:Efeito importado como bloco tecnico|Referencia magica importada):',
    re.I,
)
MEASURE_RE = re.compile(r'(?<![\w])(?P<num>\d+(?:\.\d+)?)\s*(?:feet|foot|ft\.?)(?![\w])', re.I)


def _format_meters(feet):
    # Os livros do projeto adotam a conversão prática de D&D: 5 pés = 1,5 m.
    meters = feet * 0.3
    rounded = round(meters * 2) / 2
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded).replace('.', ',')


def _protect_measurements(text, namespace=''):
    values = []

    def replace(match):
        feet = float(match.group('num'))
        feet_label = str(int(feet)) if feet.is_integer() else str(feet)
        values.append(f'{_format_meters(feet)} m [{feet_label} pés]')
        return f'ZXQ{namespace}MEASURE{len(values) - 1:05d}QXZ'

    return MEASURE_RE.sub(replace, text or ''), values


def _restore_measurements(text, values, namespace=''):
    for index, value in enumerate(values):
        text = text.replace(f'ZXQ{namespace}MEASURE{index:05d}QXZ', value)
    return text


LOCALIZED_MEASURE_RE = re.compile(
    r'\d+(?:[,.]\d+)?\s*m\s*\[(?P<feet>\d+(?:[,.]\d+)?)\s*(?:pes|pés|ft\.?)\]',
    re.I,
)


def _normalize_translated_text(text):
    """Mantém a apresentação mecânica estável mesmo para traduções em cache."""
    def replace(match):
        feet = float(match.group('feet').replace(',', '.'))
        feet_label = str(int(feet)) if feet.is_integer() else str(feet).replace('.', ',')
        return f'{_format_meters(feet)} m [{feet_label} pés]'

    text = LOCALIZED_MEASURE_RE.sub(replace, text or '')
    text = re.sub(
        r'resistência à magia\s+CD\s*(\d+)',
        r'CD de resistência de magia \1',
        text,
        flags=re.I,
    )
    return text.strip()


def _split_text(text, limit=360):
    """Quebra prosa longa em sentencas sem partir notacoes mecanicas no meio."""
    text = (text or '').strip()
    if len(text) <= limit:
        return [text]
    parts = []
    remaining = text
    while len(remaining) > limit:
        candidates = [
            remaining.rfind(separator, 0, limit)
            for separator in ('\n\n', '. ', '; ', ': ', ', ', ' ')
        ]
        cut = max(candidates)
        if cut < limit // 2:
            cut = limit
        elif remaining[cut:cut + 2] in ('\n\n', '. ', '; ', ': ', ', '):
            cut += 2
        else:
            cut += 1
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


class Translator:
    google_endpoint = 'https://translate.googleapis.com/translate_a/single'
    memory_endpoint = 'https://api.mymemory.translated.net/get'
    simply_endpoints = (
        'https://st.privacydev.net/api/translate/',
        'https://simplytranslate.org/api/translate/',
    )

    def __init__(self, cache_path, enabled):
        self.cache_path = cache_path
        self.enabled = enabled
        if cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding='utf-8'))
        else:
            self.cache = {}
        self.changed = False

    def translate(self, text):
        text = (text or '').strip()
        if not text:
            return ''
        if text in self.cache:
            return self.cache[text]
        if not self.enabled:
            return ''

        self.translate_many([text])
        return self.cache.get(text, '')

    def _request_google(self, text):
        payload = urllib.parse.urlencode({
            'client': 'gtx', 'sl': 'en', 'tl': 'pt', 'dt': 't', 'q': text,
        }).encode('utf-8')
        request = urllib.request.Request(
            self.google_endpoint,
            data=payload,
            headers={'User-Agent': 'Bonfire-Tales-Content-Refiner/1.0'},
        )
        last_error = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = json.load(response)
                return ''.join(chunk[0] for chunk in data[0] if chunk and chunk[0])
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise CommandError(f'Falha ao traduzir bloco depois de 4 tentativas: {last_error}')

    def _request_memory(self, text):
        if len(text) > 450:
            raise CommandError('Lote excede o limite do tradutor alternativo.')
        params = {
            'q': text,
            'langpair': 'en|pt',
        }
        contact = __import__('os').environ.get('BONFIRE_TRANSLATION_CONTACT', '').strip()
        if contact:
            params['de'] = contact
        url = self.memory_endpoint + '?' + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'Bonfire-Tales-Content-Refiner/1.0'},
        )
        last_error = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = json.load(response)
                if int(data.get('responseStatus') or 0) != 200:
                    raise ValueError(data.get('responseDetails') or 'resposta sem sucesso')
                return (data.get('responseData') or {}).get('translatedText') or ''
            except Exception as exc:
                last_error = exc
                time.sleep(2 * (attempt + 1))
        raise CommandError(f'Falha no tradutor alternativo depois de 4 tentativas: {last_error}')

    def _request_simply(self, text):
        last_error = None
        for endpoint in self.simply_endpoints:
            url = endpoint + '?' + urllib.parse.urlencode({
                'engine': 'google', 'from': 'en', 'to': 'pt', 'text': text,
            })
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Bonfire-Tales-Content-Refiner/1.0'},
            )
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        data = json.load(response)
                    translated = data.get('translated_text') or data.get('translated-text') or ''
                    if not translated:
                        raise ValueError('resposta sem traducao')
                    return translated
                except Exception as exc:
                    last_error = exc
                    time.sleep(1.2 * (attempt + 1))
        raise CommandError(f'Falha no tradutor em lote depois de 4 tentativas: {last_error}')

    def _request(self, text):
        try:
            return self._request_simply(text)
        except CommandError:
            if len(text) <= 450:
                return self._request_memory(text)
            raise

    def translate_many(self, texts):
        original_pending = list(dict.fromkeys(
            text.strip() for text in texts
            if text and text.strip() and text.strip() not in self.cache
        ))
        if not original_pending or not self.enabled:
            return

        segments = {}
        pending = []
        for source in original_pending:
            chunks = _split_text(source)
            segments[source] = chunks
            pending.extend(chunk for chunk in chunks if chunk not in self.cache)
        pending = list(dict.fromkeys(pending))

        chunks = []
        current = []
        current_size = 0
        for index, source in enumerate(pending):
            namespace = f'B{index:06d}'
            protected, measures = _protect_measurements(source, namespace)
            marker = f'ZXQBLOCK{index:06d}QXZ'
            entry = (index, source, namespace, measures, marker, protected)
            entry_size = len(marker) + len(protected) + 4
            if current and current_size + entry_size > 3200:
                chunks.append(current)
                current = []
                current_size = 0
            current.append(entry)
            current_size += entry_size
        if current:
            chunks.append(current)

        for chunk in chunks:
            def request_chunk(entries):
                payload = '\n'.join(f'{entry[4]}\n{entry[5]}' for entry in entries)
                try:
                    translated = self._request(payload)
                except CommandError:
                    if len(entries) <= 1:
                        raise
                    middle = len(entries) // 2
                    values = request_chunk(entries[:middle])
                    values.update(request_chunk(entries[middle:]))
                    return values
                markers = list(re.finditer(r'ZXQBLOCK(\d{6})QXZ\s*', translated))
                values = {}
                for position, marker_match in enumerate(markers):
                    start = marker_match.end()
                    end = markers[position + 1].start() if position + 1 < len(markers) else len(translated)
                    values[int(marker_match.group(1))] = translated[start:end].strip()
                return values

            values = request_chunk(chunk)
            expected = {entry[0] for entry in chunk}
            if set(values) != expected:
                # Alguns provedores alteram um marcador em lotes com notacao muito
                # densa. Repetir cada entrada isolada elimina a ambiguidade sem
                # descartar todo o progresso anterior.
                values = {}
                for entry in chunk:
                    single = request_chunk([entry])
                    if entry[0] not in single:
                        raise CommandError(
                            f'O servico de traducao alterou o marcador do bloco {entry[0]}.'
                        )
                    values.update(single)
            for index, source, namespace, measures, _marker, _protected in chunk:
                self.cache[source] = _restore_measurements(values[index], measures, namespace)
                self.changed = True
            self.save()

        for source, source_segments in segments.items():
            if all(segment in self.cache for segment in source_segments):
                self.cache[source] = ' '.join(self.cache[segment].strip() for segment in source_segments)
                self.changed = True
        self.save()

    def save(self):
        if not self.changed:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        self.changed = False


def _block_key(block):
    return (block.get('name_en') or block.get('name') or '').strip().casefold()


def _normalized_feature_base(value):
    return re.sub(r'\s*\([^)]*\)\s*$', '', value or '').strip().casefold()


ENGLISH_FEATURE_SUFFIX_RE = re.compile(
    r'\b(?:and|after|day|form|in|lair|long|only|or|recharge|recharges|requires|rest|short|turn)\b',
    re.I,
)


def _feature_suffix_needs_translation(value):
    match = re.search(r'\(([^)]*)\)\s*$', value or '')
    return bool(match and ENGLISH_FEATURE_SUFFIX_RE.search(match.group(1)))


def _feature_name_candidate(source, translator):
    """Traduz o rótulo sem substituir nomes editoriais já revisados à mão."""
    english = (source.get('name_en') or '').strip()
    imported = (source.get('name') or english).strip()
    if not english:
        return imported
    if (
        _normalized_feature_base(imported) != _normalized_feature_base(english)
        and not _feature_suffix_needs_translation(imported)
    ):
        return imported
    translated = (translator.translate(english) or '').strip()
    if not translated:
        return imported
    return translated[:1].upper() + translated[1:]


def _merge_block(existing, source, translator):
    merged = dict(existing or {})
    previous_english = '\n\n'.join(
        part.strip() for part in merged.get('entries_en', [])
        if isinstance(part, str) and part.strip()
    )
    for key in ('name_en', 'spell_refs', 'spell_uses'):
        if source.get(key):
            merged[key] = source[key]
        elif key in ('spell_refs', 'spell_uses'):
            merged.pop(key, None)

    # ``cast{}`` é sempre derivado das referências do texto oficial. Tags de
    # ataque/efeito cadastradas pela equipe continuam intocadas.
    manual_tags = [
        tag for tag in (merged.get('tags') or [])
        if not str(tag).strip().startswith('cast{')
    ]
    derived_tags = list(source.get('tags') or [])
    if manual_tags or derived_tags:
        merged['tags'] = list(dict.fromkeys([*manual_tags, *derived_tags]))
    else:
        merged.pop('tags', None)
    candidate_name = _feature_name_candidate(source, translator)
    current_name = (merged.get('name') or '').strip()
    source_english = (source.get('name_en') or '').strip()
    source_imported = (source.get('name') or '').strip()
    replaceable_names = {
        source_english.casefold(),
        _normalized_feature_base(source_english),
        source_imported.casefold(),
        _normalized_feature_base(source_imported),
        _normalized_feature_base(candidate_name),
    }
    if candidate_name and (
        not current_name
        or current_name.casefold() in replaceable_names
        or _normalized_feature_base(current_name) in replaceable_names
    ):
        merged['name'] = candidate_name

    english = '\n\n'.join(
        part.strip() for part in source.get('entries_en', source.get('entries', []))
        if isinstance(part, str) and part.strip()
    )
    merged['entries_en'] = [english] if english else []
    current_entries = [part for part in merged.get('entries', []) if isinstance(part, str)]
    current_text = '\n\n'.join(current_entries).strip()
    needs_text = not current_text or PLACEHOLDER_RE.match(current_text)
    source_changed = bool(previous_english and previous_english != english)
    if (needs_text or source_changed) and english:
        translated = translator.translate(english)
        merged['entries'] = [_normalize_translated_text(translated or english)]
    elif current_entries:
        merged['entries'] = [_normalize_translated_text(part) for part in current_entries]
    return merged


def _refine_aarakocra_aeromancer(statblock):
    """Corrige o exemplo conhecido sem confundir uma magia citada com um ataque."""
    actions = statblock.get('actions') or []
    for action in actions:
        key = _block_key(action)
        if key == 'multiattack':
            action['tags'] = [
                'instant{attacks:=2, attack:defined{wind_staff}}',
                'cast{spell:lufada-de-vento}',
            ]
        elif key == 'wind staff':
            action['tags'] = [
                'instant{attack:{melee | ranged}, attack:+5, reach:5ft, '
                'range:120ft, target:creature, dmg:1d8+3(concussao), '
                'dmg:2d10(eletrico)}'
            ]
    return statblock


def _merge_sections(statblock, parsed, translator):
    for _csv_name, json_name, _label in SECOES:
        source_blocks = parsed.get(json_name) or []
        existing_blocks = statblock.get(json_name) or []
        by_key = {_block_key(block): block for block in existing_blocks if isinstance(block, dict)}
        merged = []
        for source in source_blocks:
            existing = by_key.get(_block_key(source), {})
            merged.append(_merge_block(existing, source, translator))
        if source_blocks:
            statblock[json_name] = merged
    return statblock


class Command(BaseCommand):
    help = 'Substitui placeholders do bestiario pelo texto integral traduzido, sem sobrescrever tags.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default=str(CSV_PATH))
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--translate', action='store_true')
        parser.add_argument('--limite', type=int, default=0)
        parser.add_argument('--slug', action='append', default=[])
        parser.add_argument('--offset', type=int, default=0)
        parser.add_argument(
            '--cache',
            default='scratch/import_livros/cache_bestiario_pt.json',
            help='Cache local de traducoes; scratch nao e versionado.',
        )

    def handle(self, *args, **options):
        path = _repo_path(options['csv'])
        if not path.exists():
            raise CommandError(f'CSV nao encontrado: {path}')

        cache_path = _repo_path(options['cache'])
        translator = Translator(cache_path, enabled=options['translate'])
        spell_alignment = _resolve_spell_alignment(_load_spell_alignment())
        catalog = _spell_catalog(spell_alignment)
        wanted = set(options['slug'])

        with path.open(newline='', encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        if wanted:
            rows = [row for row in rows if _slug_criatura(row['Name']) in wanted]
        if options['offset']:
            rows = rows[options['offset']:]
        if options['limite']:
            rows = rows[:options['limite']]

        parsed_rows = []
        texts_to_translate = []
        for row in rows:
            parsed = {
                json_name: _split_secao(row.get(csv_name, ''), catalog)
                for csv_name, json_name, _label in SECOES
            }
            parsed_rows.append((row, parsed))
            for blocks in parsed.values():
                for block in blocks:
                    name_en = (block.get('name_en') or '').strip()
                    name = (block.get('name') or '').strip()
                    if name_en and (
                        _normalized_feature_base(name) == _normalized_feature_base(name_en)
                        or _feature_suffix_needs_translation(name)
                    ):
                        texts_to_translate.append(name_en)
                    texts_to_translate.extend(block.get('entries_en') or [])
        translator.translate_many(texts_to_translate)

        found = updated = missing = 0
        context = transaction.atomic() if options['apply'] else transaction.atomic()
        with context:
            for row, parsed in parsed_rows:
                slug = _slug_criatura(row['Name'].strip())
                creature = (
                    TbBestiario.objects.filter(slug=slug).first()
                    or TbBestiario.objects.filter(statblock_json__name_en=row['Name'].strip()).first()
                )
                if not creature:
                    missing += 1
                    continue
                found += 1
                statblock = dict(creature.statblock_json or {})
                before = json.dumps(statblock, ensure_ascii=False, sort_keys=True)
                statblock = _merge_sections(statblock, parsed, translator)
                if slug == 'aarakocra-aeromancer':
                    statblock = _refine_aarakocra_aeromancer(statblock)
                after = json.dumps(statblock, ensure_ascii=False, sort_keys=True)
                if before != after:
                    updated += 1
                    if options['apply']:
                        creature.statblock_json = statblock
                        creature.save(update_fields=['statblock_json'])
            if not options['apply']:
                transaction.set_rollback(True)

        translator.save()
        mode = 'APLICADO' if options['apply'] else 'PREVIEW'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: CSV={len(rows)} encontrados={found} atualizados={updated} ausentes={missing}'
        ))
        if not options['translate']:
            self.stdout.write('Sem --translate, apenas traducoes ja presentes no cache sao usadas.')
        self.stdout.write(f'Cache: {cache_path} ({len(translator.cache)} blocos)')
