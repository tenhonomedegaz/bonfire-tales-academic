# -*- coding: utf-8 -*-
"""Tokenizador do DSL de tags + checagem de balanceamento de delimitadores.

É a primeira barreira estilo-Excel: uma fórmula com '{' ou '(' aberto não é
avaliada — o lexer já acusa "delimitador não fechado" com a posição.
"""
import re
from collections import namedtuple

Token = namedtuple("Token", "type value pos")


class LexError(Exception):
    pass


# Ordem importa. ARROW antes de MINUS; RANGE ('..') antes de DOT.
_TOKEN_RE = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<STRING>"[^"]*")
    | (?P<ARROW>->)
    | (?P<RANGE>\.\.)
    | (?P<LBRACE>\{) | (?P<RBRACE>\})
    | (?P<LPAREN>\() | (?P<RPAREN>\))
    | (?P<LBRACK>\[) | (?P<RBRACK>\])
    | (?P<COMMA>,)
    | (?P<CMP><=|>=|<|>)
    | (?P<COLON>:) | (?P<EQ>=) | (?P<DOT>\.)
    | (?P<PIPE>\|) | (?P<BANG>!) | (?P<AT>@)
    | (?P<OP>[+*/]) | (?P<MINUS>-)
    | (?P<WORD>[A-Za-z0-9_À-ɏ][A-Za-z0-9_À-ɏ'-]*)
    | (?P<OTHER>.)
    """,
    re.VERBOSE,
)

_OPEN = {"LBRACE": "}", "LPAREN": ")", "LBRACK": "]"}
_MATCH = {"RBRACE": "{", "RPAREN": "(", "RBRACK": "["}


def tokenize(text):
    """Quebra `text` em Tokens (descartando espaços). Não falha em delimitadores;
    quem reporta o balanceamento é check_balance()."""
    out = []
    for m in _TOKEN_RE.finditer(text):
        kind = m.lastgroup
        if kind == "WS":
            continue
        out.append(Token(kind, m.group(), m.start()))
    return out


def check_balance(tokens, text=""):
    """Retorna lista de erros de balanceamento: [(pos, msg), ...]."""
    errors = []
    stack = []  # (type, pos)
    for t in tokens:
        if t.type in _OPEN:
            stack.append(t)
        elif t.type in _MATCH:
            if not stack:
                errors.append((t.pos, f"'{t.value}' fechando sem abrir"))
            else:
                top = stack.pop()
                want = _OPEN[top.type]
                if t.value != want:
                    errors.append((t.pos, f"'{t.value}' fecha '{top.value}' aberto na posição {top.pos} (esperado '{want}')"))
    for t in stack:
        want = _OPEN[t.type]
        errors.append((t.pos, f"'{t.value}' aberto na posição {t.pos} nunca fechado (falta '{want}')"))
    return errors


def find_other(tokens):
    """Caracteres inesperados (não previstos pela gramática)."""
    return [(t.pos, t.value) for t in tokens if t.type == "OTHER"]
