"""Bounded reader for the bot's existing LOG/Aventuras spreadsheet convention."""
import hashlib
import io
import re
import unicodedata
import zipfile
from itertools import islice
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.exceptions import ValidationError

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 6000
MAX_RECORDS = 400
SHEET_ID = re.compile(r'[A-Za-z0-9_-]{20,160}')


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).casefold().strip()


CATEGORY_LABELS = {
    'mission': 'Missao', 'staff_bonus': 'Salario / bonificacao da staff',
    'server_boost': 'Bonificacao Server Boost', 'mm_redemption': 'Resgate de Moedas de Mestre',
    'event_exchange': 'Troca de Moeda de Evento', 'adjustment': 'Outro ajuste / bonus',
}


def entry_category(title, master=''):
    """A classification hint is not proof, regardless of who the row calls master."""
    text = folded(title)
    if re.search(r'\b(?:moedas? de evento|moedas? evento|braseiros? via evento)\b', text):
        return 'event_exchange'
    if re.search(r'\b(?:moedas? de mestre|moedas? de mestragem|resgate mm)\b', text):
        return 'mm_redemption'
    if re.search(r'\b(?:nitro|server boost(?:er)?|servidor boost|boost discord)\b', text):
        return 'server_boost'
    if re.search(r'\b(?:fgts|salario)\b', text) or (
            'staff' in text and re.match(r'^(?:bonus|bonificacao)\b', text)):
        return 'staff_bonus'
    if re.match(r'^(?:boost(?:er)?|superboost|bonus|bonificacao|token)\b', text):
        return 'adjustment'
    return 'mission'


def spreadsheet_id(value):
    if not isinstance(value, str):
        return ''
    if SHEET_ID.fullmatch(value):
        return value
    try:
        url = urlsplit(value)
        match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]{20,160})(?:/.*)?', url.path)
        return match[1] if (url.scheme == 'https' and url.netloc == 'docs.google.com' and match) else ''
    except ValueError:
        return ''


class _GoogleRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urlsplit(newurl)
        if (url.scheme != 'https' or url.port not in (None, 443) or url.username or url.password
                or not (url.hostname == 'docs.google.com' or
                        (url.hostname or '').endswith('.googleusercontent.com'))):
            raise ValidationError('Redirecionamento da planilha recusado.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_workbook(source_id):
    if not isinstance(source_id, str) or not SHEET_ID.fullmatch(source_id):
        raise ValidationError('Identificador de planilha invalido.')
    url = f'https://docs.google.com/spreadsheets/d/{source_id}/export?format=xlsx'
    try:
        with build_opener(_GoogleRedirects()).open(Request(url, headers={
                'User-Agent': 'Bonfire-Character-History/1.0'}), timeout=20) as response:
            data = response.read(MAX_BYTES + 1)
    except (URLError, TimeoutError, OSError):
        raise ValidationError('Nao foi possivel ler a planilha. Confira o acesso de leitura '
                              'ou envie o XLSX neste painel; nao foi alterado nenhum dado.') from None
    if len(data) > MAX_BYTES or not data.startswith(b'PK'):
        raise ValidationError('A resposta nao e um XLSX acessivel ou excede 8 MB.')
    return data


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if len(raw) > 32:
        return None
    try:
        result = Decimal(raw.replace(',', '.'))
        return int(result) if result.is_finite() and 0 <= result <= 100000 and result == int(result) else None
    except (ValueError, InvalidOperation, OverflowError):
        return None


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(value or '').strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def read_workbook(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValidationError('Envie um XLSX de ate 8 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.infolist()
            if (len(files) > 1500 or sum(f.file_size for f in files) > 48 * 1024 * 1024
                    or any(f.filename.lower().endswith('vbaproject.bin') for f in files)):
                raise ValidationError('Arquivo excede os limites ou contem macros.')
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
    except (zipfile.BadZipFile, OSError, ValueError, KeyError):
        raise ValidationError('Arquivo XLSX invalido.') from None
    try:
        if not {'LOG', 'Aventuras'}.issubset(book.sheetnames):
            raise ValidationError('Formato desconhecido: sao necessarias as abas LOG e Aventuras.')
        log = book['LOG']
        metadata = {'character_name': str(log['C6'].value or '').strip()[:300],
                    'rank_name': str(log['R25'].value or '').strip()[:200],
                    'class_name': str(log['T5'].value or '').strip()[:200],
                    'level': _number(log['AL6'].value),
                    'adventures_reported': _number(log['AE7'].value)}
        if not metadata['character_name']:
            raise ValidationError('LOG!C6 nao tem nome legivel. Formulas precisam de resultado salvo no XLSX.')
        sheet = book['Aventuras']
        if sheet.max_row and sheet.max_row > MAX_ROWS:
            raise ValidationError('Aba Aventuras excede 6000 linhas; nenhuma importacao parcial foi feita.')
        # Google exports can omit worksheet dimensions. Never treat that as one row.
        cells = list(islice(sheet.iter_rows(min_row=1, max_col=64, values_only=True), MAX_ROWS + 1))
        if len(cells) > MAX_ROWS:
            raise ValidationError('Aba Aventuras excede 6000 linhas; nenhuma importacao parcial foi feita.')
        rows, warnings = [], []
        for start in range(3, len(cells) + 1, 15):
            title = str(cells[start - 1][9] or '').strip()[:500]
            if not title:
                continue
            if len(rows) >= MAX_RECORDS:
                raise ValidationError('Mais de 400 registros; nenhuma importacao parcial foi feita.')
            fields = {}
            for line in cells[start - 1:start + 14]:
                for col, cell in enumerate(line):
                    if not isinstance(cell, str) or len(cell) > 80:
                        continue
                    label = folded(cell).rstrip(':')
                    field = {'data': 'date', 'data da missao': 'date', 'mestre': 'master',
                             'aventuras': 'adventures', 'numero de aventuras': 'adventures',
                             'quantidade de aventuras': 'adventures', 'resumo': 'summary',
                             'total de riqueza ganha': 'wealth_gained',
                             'total de riqueza gasta': 'wealth_spent',
                             'missao especial gasta': 'special_spent', 'boost gasto': 'boost_spent',
                             'braseiros ganhos': 'embers_gained',
                             'moedas de evento gastas': 'event_coins_spent'}.get(label)
                    if field:
                        value = None
                        for candidate in line[col + 1:]:
                            if isinstance(candidate, str) and candidate.strip().endswith(':'):
                                break  # A neighboring field label is not this field's value.
                            if candidate is not None and str(candidate).strip():
                                value = candidate
                                break
                        if value is not None:
                            fields[field] = value
            category = entry_category(title, fields.get('master'))
            rows.append({'key': f'Aventuras!J{start}', 'title': title,
                         'kind': 'mission' if category == 'mission' else 'adjustment', 'category': category,
                         'date': _day(fields.get('date')), 'master': str(fields.get('master') or '')[:200],
                         'date_raw': str(fields.get('date') or '')[:100],
                         'date_storage': type(fields.get('date')).__name__,
                         'adventures': _number(fields.get('adventures')),
                         'summary': str(fields.get('summary') or '')[:3000],
                         'declared_rewards': {key: str(fields[key])[:120] for key in
                             ('wealth_gained', 'wealth_spent', 'special_spent', 'boost_spent',
                              'embers_gained', 'event_coins_spent') if key in fields},
                         'starter_marker': str(cells[start + 1][22] or '')[:100] if start + 1 < len(cells) else ''})
        if not rows:
            warnings.append('Nenhuma missao legivel nos blocos de Aventuras; nao inferir ausencia de historico.')
        if any(row['kind'] == 'mission' and row['adventures'] is None for row in rows):
            warnings.append('Quantidades sem rotulo explicito ficam desconhecidas; valores financeiros nao viram aventuras.')
        return {'format': 'bot-log-v1', 'file_hash': hashlib.sha256(data).hexdigest(),
                'metadata': metadata, 'rows': rows, 'warnings': warnings}
    finally:
        book.close()
