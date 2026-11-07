"""Player-facing terminology only. Never rewrite saved rules or mechanical keys."""
import re

_TERM = re.compile(r'\b(?:(as|das|nas|às|pelas|a|da|na|à|pela|uma|outra)\s+)?(salvaguardas?)\b', re.I)
_ARTICLES = {'as':'os','das':'dos','nas':'nos','às':'aos','pelas':'pelos',
             'a':'o','da':'do','na':'no','à':'ao','pela':'pelo','uma':'um','outra':'outro'}
_PROTECTED = re.compile(r'```[\s\S]*?```|`[^`\n]*`|<[^>]*>|https?://[^\s<>]+|\]\([^\n)]*\)',re.I)


def rules_terms(value):
    text = str(value or '')
    def replace(match):
        article, term = match.groups()
        replacement = 'testes de resistência' if term.lower().endswith('s') else 'teste de resistência'
        if term.isupper(): replacement = replacement.upper()
        elif term[0].isupper(): replacement = replacement[0].upper()+replacement[1:]
        if article:
            prefix = _ARTICLES[article.lower()]
            if article.isupper() and term.isupper(): prefix = prefix.upper()
            elif article[0].isupper(): prefix = prefix.capitalize()
            replacement = prefix+' '+replacement
        return replacement
    out=[]; cursor=0
    for protected in _PROTECTED.finditer(text):
        out.extend((_TERM.sub(replace,text[cursor:protected.start()]),protected.group()))
        cursor=protected.end()
    out.append(_TERM.sub(replace,text[cursor:]))
    return ''.join(out)
