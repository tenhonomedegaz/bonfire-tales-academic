"""Bounded, read-only XLSX exports of explicitly allowed catalog data."""
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from tempfile import SpooledTemporaryFile

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill

from . import models as catalog
from .db_access import MODEL_ALLOWLIST

MAX_TABLES = 12
MAX_ROWS_PER_TABLE = 10000
MAX_TOTAL_ROWS = 50000
MAX_CELLS = 500000
MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_FILTERS = 8
_XML_UNSAFE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


class ExportError(ValueError):
    pass


@dataclass(frozen=True)
class ExportAccess:
    model: type
    fields: tuple


EXPORT_MODELS = {name: ExportAccess(access.model, access.readable)
                 for name, access in MODEL_ALLOWLIST.items()}
# Catalogs, not player/authentication/financial tables. New entries are opt-in.
for _model in (catalog.TbClasse, catalog.TbSubclasse, catalog.TbClassehabilidade,
               catalog.TbRecursoclasse, catalog.TbAntecedente, catalog.TbEssencia,
               catalog.TbTracoracial, catalog.TbArmadilha, catalog.TbConteudoEstatico):
    EXPORT_MODELS[_model._meta.model_name] = ExportAccess(
        _model, tuple(field.name for field in _model._meta.concrete_fields
                      if not isinstance(field, (models.BinaryField, models.FileField))))


def _field(access, name):
    if not isinstance(name, str) or name not in access.fields:
        raise ExportError('Campo nao permitido.')
    return access.model._meta.get_field(name)


def _operators(field):
    if isinstance(field, (models.JSONField, models.BinaryField)):
        return []
    return ['exact', 'icontains'] if isinstance(field, (models.CharField, models.TextField)) else ['exact']


def schema():
    result = []
    for name, access in EXPORT_MODELS.items():
        fields = []
        for column in access.fields:
            field = _field(access, column)
            fields.append({'name': column, 'label': str(field.verbose_name),
                           'primary': field.primary_key,
                           'boolean': isinstance(field, models.BooleanField),
                           'date': isinstance(field, models.DateField),
                           'operators': _operators(field)})
        result.append({'name': name, 'label': str(access.model._meta.verbose_name_plural),
                       'table': access.model._meta.db_table, 'fields': fields})
    return sorted(result, key=lambda row: row['label'].casefold())


def _period(queryset, access, spec):
    name = spec.get('date_field') or ''
    start, end = spec.get('from') or '', spec.get('to') or ''
    if not name:
        if start or end:
            raise ExportError('Selecione o campo de data para filtrar o periodo.')
        return queryset
    field = _field(access, name)
    if not isinstance(field, models.DateField):
        raise ExportError('Este campo nao permite filtro por periodo.')
    try:
        dates = [parse_date(value) if value else None for value in (start, end)]
    except (TypeError, ValueError):
        raise ExportError('Data invalida; use AAAA-MM-DD.') from None
    if any(raw and value is None for raw, value in zip((start, end), dates)):
        raise ExportError('Data invalida; use AAAA-MM-DD.')
    if all(dates) and dates[0] > dates[1]:
        raise ExportError('O inicio do periodo deve ser anterior ao fim.')
    for value, operator in zip(dates, ('gte', 'lte')):
        if value is None:
            continue
        if isinstance(field, models.DateTimeField):
            if operator == 'lte':
                try:
                    value += timedelta(days=1)
                except OverflowError:
                    raise ExportError('Data final fora do intervalo suportado.') from None
                operator = 'lt'
            value = datetime.combine(value, time.min)
            if timezone.is_aware(timezone.now()):
                value = timezone.make_aware(value, timezone.get_current_timezone())
        queryset = queryset.filter(**{name + '__' + operator: value})
    return queryset


def prepare(spec):
    if not isinstance(spec, dict) or set(spec) != {'tables'}:
        raise ExportError('Selecao de exportacao invalida.')
    tables = spec['tables']
    if not isinstance(tables, list) or not 1 <= len(tables) <= MAX_TABLES:
        raise ExportError('Selecione de 1 a %d tabelas.' % MAX_TABLES)
    result, seen, total, cells = [], set(), 0, 0
    for table in tables:
        if not isinstance(table, dict) or set(table) - {'model', 'fields', 'filters', 'date_field', 'from', 'to'}:
            raise ExportError('Configuracao de tabela invalida.')
        name = table.get('model')
        if not isinstance(name, str) or name not in EXPORT_MODELS or name in seen:
            raise ExportError('Tabela nao permitida ou repetida.')
        seen.add(name)
        access = EXPORT_MODELS[name]
        columns = table.get('fields')
        if (not isinstance(columns, list) or not columns or len(columns) > len(access.fields)
                or any(not isinstance(column, str) for column in columns)
                or len(set(columns)) != len(columns)):
            raise ExportError('Selecione campos distintos para cada tabela.')
        for column in columns:
            _field(access, column)
        columns = list(dict.fromkeys([access.model._meta.pk.name] + columns))
        queryset = access.model._default_manager.order_by(access.model._meta.pk.name)
        filters = table.get('filters', [])
        if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
            raise ExportError('Limite de %d filtros por tabela.' % MAX_FILTERS)
        for condition in filters:
            if not isinstance(condition, dict) or set(condition) != {'field', 'op', 'value'}:
                raise ExportError('Filtro invalido.')
            field = _field(access, condition['field'])
            operator = condition['op']
            if not isinstance(operator, str) or operator not in _operators(field):
                raise ExportError('Operacao de filtro nao permitida.')
            value = condition['value']
            if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 500:
                raise ExportError('Valor de filtro invalido ou muito longo.')
            if isinstance(value, float) and not math.isfinite(value):
                raise ExportError('Valor numerico invalido.')
            try:
                converter = field.target_field if isinstance(field, models.ForeignKey) else field
                value = str(value) if operator == 'icontains' else converter.to_python(value)
            except (ValidationError, ValueError, TypeError):
                raise ExportError('Valor incompativel com o campo do filtro.') from None
            queryset = queryset.filter(**{field.name + '__' + operator: value})
        queryset = _period(queryset, access, table)
        count = queryset[:MAX_ROWS_PER_TABLE + 1].count()
        if count > MAX_ROWS_PER_TABLE:
            raise ExportError('A tabela %s excede %d linhas; refine os filtros.' % (name, MAX_ROWS_PER_TABLE))
        total += count
        cells += (count + 1) * len(columns)
        if total > MAX_TOTAL_ROWS or cells > MAX_CELLS:
            raise ExportError('Exportacao muito grande; selecione menos tabelas, campos ou registros.')
        result.append({'name': name, 'access': access, 'columns': columns,
                       'queryset': queryset, 'count': count, 'selection': table})
    return result


def preview(prepared):
    return [{'model': row['name'], 'table': row['access'].model._meta.db_table,
             'count': row['count'], 'fields': row['columns'],
             'sample': [[str(_scalar(value))[:240] if value is not None else '' for value in values]
                        for values in row['queryset'].values_list(*row['columns'])[:3]]}
            for row in prepared]


def _scalar(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value) if len(str(abs(value))) > 15 else value
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _cell(sheet, value, header=False):
    cell = WriteOnlyCell(sheet, value=value)
    if isinstance(value, str):
        # Explicit text cells, even for =, +, -, @: never execute catalog content.
        cell.data_type = 's'
    if header:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='792727')
    cell.alignment = Alignment(vertical='top', wrap_text=True)
    return cell


def build_workbook(prepared, owner_id):
    workbook = Workbook(write_only=True)
    stream = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    metadata = workbook.create_sheet('_exportacao')
    metadata.append(['Gerado em', timezone.now().isoformat()])
    metadata.append(['Gerado por (ID)', str(owner_id)])
    metadata.append(['Notas', 'Somente leitura; nao e um backup restauravel. PK/FK sao IDs. '
                     'Datas ISO 8601; decimais e IDs longos sao texto. Celulas vazias representam null/vazio. '
                     'Textos acima de 30000 unidades UTF-16 ficam na aba _textos_longos. '
                     'Caracteres XML invalidos sao preservados como JSON_TEXT: seguido de string JSON.'])
    metadata.append(['Catalogo', 'Tabela', 'Linhas', 'Campos', 'Filtros e periodo'])
    overflow = None
    total_bytes, total_cells = 0, 0
    try:
        for row in prepared:
            sheet = workbook.create_sheet(row['name'][:31])
            sheet.freeze_panes = 'A2'
            from openpyxl.utils import get_column_letter
            for index, column in enumerate(row['columns'], 1):
                sheet.column_dimensions[get_column_letter(index)].width = 28
            sheet.append([_cell(sheet, column, True) for column in row['columns']])
            pk_index = row['columns'].index(row['access'].model._meta.pk.name)
            written = 0
            for values in row['queryset'].values_list(*row['columns']).iterator(chunk_size=200):
                written += 1
                if written > row['count']:
                    raise ExportError('Os registros mudaram desde a previa; atualize a previa.')
                cells = []
                for column, raw in zip(row['columns'], values):
                    value = _scalar(raw)
                    if isinstance(value, str):
                        if _XML_UNSAFE.search(value):
                            value = 'JSON_TEXT:' + json.dumps(value, ensure_ascii=True)
                        total_bytes += len(value.encode('utf-8'))
                        if total_bytes > MAX_TEXT_BYTES:
                            raise ExportError('Textos excedem 32 MiB; refine a selecao.')
                        if len(value.encode('utf-16-le')) // 2 > 30000:
                            if overflow is None:
                                overflow = workbook.create_sheet('_textos_longos')
                                overflow.freeze_panes = 'A2'
                                overflow.append(['aba', 'pk', 'linha_excel', 'campo', 'parte', 'total_partes', 'texto'])
                            chunks = [value[start:start + 15000] for start in range(0, len(value), 15000)]
                            for number, chunk in enumerate(chunks, 1):
                                overflow.append([_cell(overflow, item) for item in
                                    [sheet.title, str(values[pk_index]), written + 1, column, number, len(chunks), chunk]])
                                total_cells += 7
                            value = '@texto:%s:%d:%s' % (sheet.title, written + 1, column)
                    cells.append(_cell(sheet, value))
                total_cells += len(cells)
                if total_cells > MAX_CELLS:
                    raise ExportError('Exportacao excede o limite de celulas; refine a selecao.')
                sheet.append(cells)
            if written != row['count']:
                raise ExportError('Os registros mudaram desde a previa; atualize a previa.')
            sheet.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(row['columns'])), written + 1)
            metadata.append([_cell(metadata, value) for value in [row['name'],
                row['access'].model._meta.db_table, written, ', '.join(row['columns']),
                json.dumps(row['selection'], ensure_ascii=False)]])
        workbook.save(stream)
        stream.seek(0)
        return stream
    except Exception:
        # Saving to a discard stream closes/removes openpyxl's temporary XML files.
        try:
            with SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b') as discard:
                workbook.save(discard)
        except Exception:
            pass
        finally:
            stream.close()
            workbook.close()
        raise
