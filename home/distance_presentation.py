"""Reusable display rule: metric distance [imperial distance], never saved rules.

Missing conversions use Bonfire's existing grid scale: 1.5 m = 5 ft.
An imperial value already supplied by the author takes precedence over calculation.
Area/volume keep their dimensionality; code, HTML attributes and links stay intact.
"""
from decimal import Decimal, localcontext
import re


_NUMBER = r'[-−]?\d+(?:[.,]\d+)*'
_METRIC = r'(?:quilômetros?|quilometros?|centímetros?|centimetros?|milímetros?|milimetros?|metros?|km|cm|mm|m)'
_IMPERIAL = r'(?:polegadas?|milhas?|feet|foot|inches|inch|miles?|pés|pé|ft)'
_POWER = r'(?:\s+(?:quadrad[oa]s?|cúbic[oa]s?|cubic[oa]s?)|[²³]|\^[23]|[23])'
_END = r'(?![a-zà-öø-ÿ0-9_])'
_WORDS = {'um':'1', 'uma':'1', 'dois':'2', 'duas':'2', 'três':'3', 'tres':'3',
          'quatro':'4', 'cinco':'5', 'seis':'6', 'sete':'7', 'oito':'8',
          'nove':'9', 'dez':'10', 'meio':'0,5', 'meia':'0,5'}
_WORD_MEASUREMENT = re.compile(r'\b(' + '|'.join(_WORDS) + r')\s+(' + _METRIC + r'|' + _IMPERIAL + r')' + _END, re.I)
_EACH_MEASUREMENT = re.compile(r'\b(cada)\s+(' + _METRIC + r'|' + _IMPERIAL + r')' + _END, re.I)
_PAIR = re.compile(
    r'\s*(?:\[|\()\s*(?P<number>' + _NUMBER + r')\s*(?P<unit>' + _IMPERIAL + r')'
    r'(?P<power>' + _POWER + r')?' + _END + r'\.?\s*(?:\]|\))', re.I)
_MEASUREMENT = re.compile(
    r'(?<![\w.,])(?:'
    r'(?P<metric_values>' + _NUMBER + r'(?:\s+(?:a|até|por)\s+' + _NUMBER + r'){0,2})\s*'
    r'(?P<metric_unit>' + _METRIC + r')(?P<metric_power>' + _POWER + r')?' + _END +
    r'(?P<pairs>(?:\s*(?:\[|\()\s*' + _NUMBER + r'\s*' + _IMPERIAL + r'(?:' + _POWER + r')?' + _END + r'\.?\s*(?:\]|\))){0,3})'
    r'|(?P<imperial_number>' + _NUMBER + r')\s*(?P<imperial_unit>' + _IMPERIAL + r')(?P<imperial_power>' + _POWER + r')?' + _END +
    r')', re.I)
_PROTECTED = re.compile(
    r'```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`|<[^>]*>'
    r'|\]\((?:[^()\n]|\([^()\n]*\))*\)'
    r'|(?:https?://|www\.)[^\s<>]+', re.I)
_SLASH_PAIR = re.compile(r'(?P<metric>' + _NUMBER + r'\s*' + _METRIC + r')' + _END +
                         r'\s*/\s*(?P<imperial>' + _NUMBER + r'\s*' + _IMPERIAL + r')' + _END, re.I)
_IMPERIAL_RANGE = re.compile(r'(?<![\w.,])(?P<first>' + _NUMBER + r')\s*/\s*(?P<last>' + _NUMBER +
                             r')\s*(?P<unit>' + _IMPERIAL + r')' + _END, re.I)


def _number(value):
    value = value.replace('−', '-')
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'-?[1-9]\d{0,2}(?:\.\d{3})+', value):
        value = value.replace('.', '')
    return Decimal(value)


def _power(value):
    value = (value or '').lower()
    return 3 if re.search(r'c[úu]bic|³|3', value) else 2 if value else 1


def _metric_factor(unit):
    unit = unit.lower()
    if unit == 'km' or unit.startswith('quil'):
        return Decimal('1000')
    if unit == 'cm' or unit.startswith('cent'):
        return Decimal('.01')
    if unit == 'mm' or unit.startswith('mil'):
        return Decimal('.001')
    return Decimal(1)


def _imperial_factor(unit):
    unit = unit.lower()
    if unit.startswith(('milha', 'mile')):
        return Decimal(5280)
    if unit.startswith(('polegada', 'inch')):
        return Decimal(1) / 12
    return Decimal(1)


def _formatted(value, calculated=False):
    # Up to six fractional digits for tiny measurements; do not round to zero.
    # Keep exact decimal values supplied in the source when they terminate.
    text = format(value, 'f').rstrip('0').rstrip('.') if value != value.to_integral_value() else str(int(value))
    precision = (2 if abs(value) >= 1 else 4) if calculated else 6
    if '.' in text and len(text.split('.')[1]) > precision:
        places = max(precision, -value.copy_abs().adjusted() + 2)
        text = format(value, '.' + str(places) + 'f').rstrip('0').rstrip('.')
    return text.replace('.', ',')


def _label(value, imperial=False, power=1, calculated=False):
    singular = 0 < abs(value) <= 1
    unit = ('pé' if singular else 'pés') if imperial else ('metro' if singular else 'metros')
    if power > 1:
        unit += (' quadrado' if power == 2 else ' cúbico') + ('' if singular else 's')
    return _formatted(value, calculated=calculated) + ' ' + unit


def _dual(metric, imperial, power, imperial_calculated=False):
    return _label(metric, power=power) + ' [' + _label(imperial, imperial=True, power=power, calculated=imperial_calculated) + ']'


def _replace_measurement(match):
    with localcontext() as context:
        context.prec = 40
        if match.group('imperial_number') is not None:
            power = _power(match.group('imperial_power'))
            feet = _number(match.group('imperial_number')) * _imperial_factor(match.group('imperial_unit')) ** power
            return _dual(feet * Decimal('.3') ** power, feet, power)
        power = _power(match.group('metric_power'))
        factor = _metric_factor(match.group('metric_unit')) ** power
        pieces = re.split(r'\s+(a|até|por)\s+', match.group('metric_values'), flags=re.I)
        pairs = list(_PAIR.finditer(match.group('pairs') or ''))
        # Only pair matching dimensions; leave inconsistent source annotations
        # visible rather than silently interpreting square/cubic as linear feet.
        usable = [pair for pair in pairs if _power(pair.group('power')) == power]
        values = []
        for index, piece in enumerate(pieces):
            if index % 2:
                values.append(piece)
                continue
            metric = _number(piece) * factor
            feet = metric / Decimal('.3') ** power
            if usable and index == len(pieces) - 1:
                feet = _number(usable[0].group('number')) * _imperial_factor(usable[0].group('unit')) ** power
            values.append(_dual(metric, feet, power, imperial_calculated=not (usable and index == len(pieces) - 1)))
        result = ' '.join(values)
        for pair in pairs:
            if pair not in usable:
                result += pair.group()
        # Existing duplicated imperial annotations are consumed only if equal.
        if len(usable) > 1:
            first = _number(usable[0].group('number')) * _imperial_factor(usable[0].group('unit')) ** power
            for pair in usable[1:]:
                extra = _number(pair.group('number')) * _imperial_factor(pair.group('unit')) ** power
                if extra != first:
                    result += ' (' + _dual(extra * Decimal('.3') ** power, extra, power) + ')'
        return result


def distance_text(value):
    """Format visible distances only; preserve all other text and source markup.

    Idempotent: applying this to an already formatted card adds no second pair.
    """
    value = str(value or '')
    def format_plain(text):
        # Weapon ranges such as 20/60 ft share the unit between two values.
        text = _IMPERIAL_RANGE.sub(lambda match: match['first'] + ' ' + match['unit'] +
                                  ' / ' + match['last'] + ' ' + match['unit'], text)
        text = _SLASH_PAIR.sub(lambda match: match['metric'] + ' [' + match['imperial'] + ']', text)
        text = _WORD_MEASUREMENT.sub(lambda match: _WORDS[match[1].lower()] + ' ' + match[2], text)
        text = _EACH_MEASUREMENT.sub(lambda match: match[1] + ' 1 ' + match[2], text)
        return _MEASUREMENT.sub(_replace_measurement, text)
    pieces = []
    cursor = 0
    for match in _PROTECTED.finditer(value):
        pieces.append(format_plain(value[cursor:match.start()]))
        pieces.append(match.group())
        cursor = match.end()
    pieces.append(format_plain(value[cursor:]))
    return ''.join(pieces)
