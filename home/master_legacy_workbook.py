"""Read-only legacy market extraction. No database, formula evaluation or activation."""
import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


_MASTER = re.compile(r'^\s*(Fogueira|Fogueiira|Fogueire)\s+([0-9]+)\s*-\s*(\S.*?)\s*$', re.I)
_MAX_COMPRESSED = 8 * 1024 * 1024
_MAX_UNCOMPRESSED = 64 * 1024 * 1024
_MAX_MEMBERS = 200
_MAX_ROWS = 30000


def _normal(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).casefold().strip()


def _integer(value, *, blank_zero=False):
    if blank_zero and value in (None, ''):
        return 0
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError('Expected an integral Excel number, not text, boolean or fraction.')


def _date(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        value = value.date()
    elif isinstance(value, str):
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
            value = datetime.strptime(value, '%d/%m/%Y').date()
        elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            value = date.fromisoformat(value)
        else:
            raise ValueError('Date format is not explicit.')
    if not isinstance(value, date) or value.year < 1900:
        raise ValueError('Date is invalid or outside the Excel date range; never infer a year.')
    return value.isoformat()


def _value(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def _rows(formulas, cached, sheet, start, first, last):
    for row, (cells, values) in enumerate(zip(
            formulas[sheet].iter_rows(min_row=start, min_col=first, max_col=last),
            cached[sheet].iter_rows(min_row=start, min_col=first, max_col=last,
                                    values_only=True)), start):
        if row > _MAX_ROWS:
            raise ValueError('Worksheet exceeds the 30000-row limit.')
        raw = {f'{get_column_letter(first + i)}{row}': {
            'value': _value(cell.value), 'cached': _value(values[i]),
            'type': cell.data_type, 'number_format': cell.number_format,
        } for i, cell in enumerate(cells)}
        yield row, values, raw


def parse_workbook(file_or_path):
    """Return schema 1; invalid rows live in warnings[].quarantine, not entries.

    Balances remain cached snapshots. Deltas compare CALCs with accepted entries,
    so quarantined history can explain a difference. Blank event coins mean zero.
    Reward classifications are review labels only; every reward stays inactive.
    """
    if hasattr(file_or_path, 'read'):
        position = file_or_path.tell()
        try:
            file_or_path.seek(0)
            data = file_or_path.read(_MAX_COMPRESSED + 1)
        finally:
            file_or_path.seek(position)
    else:
        path = Path(file_or_path)
        if path.stat().st_size > _MAX_COMPRESSED:
            raise ValueError('Workbook exceeds the 8 MiB compressed limit.')
        with path.open('rb') as stream:
            data = stream.read(_MAX_COMPRESSED + 1)
    if len(data) > _MAX_COMPRESSED:
        raise ValueError('Workbook exceeds the 8 MiB compressed limit.')
    with ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > _MAX_MEMBERS:
            raise ValueError('Workbook exceeds the 200 ZIP-member limit.')
        if sum(member.file_size for member in members) > _MAX_UNCOMPRESSED:
            raise ValueError('Workbook exceeds the 64 MiB uncompressed limit.')
    result = dict(schema=1, source_sha256=hashlib.sha256(data).hexdigest(),
                  masters=[], entries=[], rewards=[], warnings=[])
    formulas = load_workbook(BytesIO(data), read_only=True, data_only=False)
    cached = None
    try:
        cached = load_workbook(BytesIO(data), read_only=True, data_only=True)
        names = {_normal(name): name for name in formulas.sheetnames}
        bau, history, calcs, rewards = [names[key] for key in (
            'bau dos mestres', 'aventuras  mercado', 'calcs', 'lista de recompensas')]

        def warn(code, source, **detail):
            result['warnings'].append(dict(code=code, source=source, **detail))

        def identity(value):
            match = _MASTER.fullmatch(value) if isinstance(value, str) else None
            return (int(match[2]), match[3], match[1]) if match else (None, None, None)

        masters, calculations = {}, {}
        for row, values, raw in _rows(formulas, cached, bau, 2, 1, 4):
            label, balance, tables, coins = values
            if label in (None, '', 0):
                continue
            source = dict(sheet=bau, row=row)
            number, name, spelling = identity(label)
            try:
                if number is None or number in masters:
                    raise ValueError('Unknown or duplicate master identity.')
                master = dict(number=number, name=name, label=label,
                    balance_mm=_integer(balance), table_count=_integer(tables),
                    event_coins=_integer(coins, blank_zero=True), source=source, raw=raw)
            except ValueError as error:
                warn('invalid_master', source, reason=str(error), quarantine={'raw': raw})
                continue
            masters[number] = master
            result['masters'].append(master)
            if spelling.casefold() != 'fogueira':
                warn('legacy_id_spelling', source, master_number=number)

        for row, values, raw in _rows(formulas, cached, calcs, 2, 1, 3):
            if values[0] in (None, '', 0):
                continue
            source = dict(sheet=calcs, row=row)
            number, _, _ = identity(values[0])
            try:
                if number not in masters or number in calculations:
                    raise ValueError('Unknown or duplicate CALCs master identity.')
                calculations[number] = dict(income=_integer(values[1]),
                    expense=_integer(values[2]), source=source, raw=raw)
            except ValueError as error:
                warn('invalid_calculation', source, reason=str(error), quarantine={'raw': raw})

        totals, quarantined = defaultdict(lambda: [0, 0]), defaultdict(int)
        for row, values, raw in _rows(formulas, cached, history, 3, 1, 10):
            for start, kind in ((1, 'adventure'), (6, 'purchase')):
                original = {key: cell for key, cell in raw.items()
                            if key in {f'{get_column_letter(c)}{row}' for c in range(start + 1, start + 5)}}
                if all(cell['value'] in (None, '') for cell in original.values()):
                    continue
                label, title, when, amount = values[start:start + 4]
                number, _, _ = identity(label)
                source = dict(sheet=history, row=row)
                entry = dict(key=f'{history}:{row}:{kind}', master_number=number,
                    kind=kind, title=title, date=None, amount_mm=None, raw=original, source=source)
                issues = []
                if number not in masters:
                    issues.append('unknown_master')
                if not isinstance(title, str) or not title.strip():
                    issues.append('invalid_title')
                try:
                    entry['date'] = _date(when)
                except ValueError:
                    issues.append('invalid_date')
                try:
                    entry['amount_mm'] = _integer(amount) * (1 if kind == 'adventure' else -1)
                except ValueError:
                    issues.append('invalid_amount')
                if issues:
                    warn('quarantined_entry', source, key=entry['key'], issues=issues, quarantine=entry)
                    quarantined[number] += 1
                    continue
                result['entries'].append(entry)
                totals[number][0 if kind == 'adventure' else 1] += (
                    entry['amount_mm'] if kind == 'adventure' else -entry['amount_mm'])

        for number, master in masters.items():
            income, expense = totals[number]
            calc = calculations.get(number, dict(income=None, expense=None))
            calc.update(entry_income=income, entry_expense=expense,
                        quarantined_entries=quarantined[number])
            for field, actual in (('income', income), ('expense', expense)):
                calc[field + '_delta'] = None if calc[field] is None else calc[field] - actual
            calc['balance_delta'] = (None if calc['income'] is None or calc['expense'] is None
                                     else master['balance_mm'] - (calc['income'] - calc['expense']))
            master['calculations'] = calc
            if number not in calculations:
                warn('missing_calculation', master['source'], master_number=number)
            elif any(calc[key] for key in ('income_delta', 'expense_delta', 'balance_delta')):
                warn('calculation_delta', master['source'], master_number=number,
                     deltas={key: calc[key] for key in ('income_delta', 'expense_delta', 'balance_delta')})

        for row, values, raw in _rows(formulas, cached, rewards, 2, 1, 3):
            if all(cell['value'] in (None, '') for cell in raw.values()):
                continue
            title, description, price = values
            try:
                fixed = _integer(price)
            except ValueError:
                fixed = None
            retired = any(word in _normal(title) for word in ('cofre', 'mestre ouro'))
            classification = 'retired' if retired else 'adapted' if fixed is not None else 'needs_review_fixed_price'
            result['rewards'].append(dict(title=title, description=description,
                price=str(price) if price is not None else None, fixed_price_mm=fixed,
                classification=classification, active=False, raw=raw, source=dict(sheet=rewards, row=row)))
        return result
    finally:
        formulas.close()
        if cached is not None:
            cached.close()
