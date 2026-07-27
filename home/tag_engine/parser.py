"""Balanced parser for the Bonfire tag language.

The grammar is intentionally permissive about operands. The parser owns
structure, nesting and order; the library/validator owns the vocabulary and
operand contracts.
"""
import re

from .lexer import check_balance, tokenize
from .nodes import TagNode, TagProgram


_IDENT = re.compile(r"[a-z_][a-z0-9_]*", re.I)


class ParseError(ValueError):
    pass


def _matching(text, opening):
    pairs = {"{": "}", "(": ")", "[": "]"}
    expected = pairs.get(text[opening])
    if expected is None:
        return -1
    stack = []
    for pos in range(opening, len(text)):
        char = text[pos]
        if char in pairs:
            stack.append(pairs[char])
        elif char in "}])":
            if not stack or char != stack[-1]:
                return -1
            stack.pop()
            if not stack:
                return pos
    return -1


def _split_top(text, separators=",;"):
    parts = []
    start = 0
    stack = []
    pairs = {"{": "}", "(": ")", "[": "]"}
    for pos, char in enumerate(text):
        if char in pairs:
            stack.append(pairs[char])
        elif char in "}])":
            if stack and char == stack[-1]:
                stack.pop()
        elif not stack and char in separators:
            parts.append((start, pos, text[start:pos]))
            start = pos + 1
    parts.append((start, len(text), text[start:]))
    return parts


def _top_operator(text):
    stack = []
    pairs = {"{": "}", "(": ")", "[": "]"}
    for pos, char in enumerate(text):
        if char in pairs:
            if not stack and char == "{":
                return pos, "block"
            stack.append(pairs[char])
        elif char in "}])":
            if stack and char == stack[-1]:
                stack.pop()
        elif not stack:
            if text.startswith(":=", pos):
                return pos, ":="
            if char == ":":
                return pos, ":"
            if char == "=":
                return pos, "="
    return -1, "flag"


def _strip_qualifiers(value):
    value = value.strip()
    qualifiers = []
    while value.endswith(")"):
        depth = 0
        opening = -1
        for pos in range(len(value) - 1, -1, -1):
            if value[pos] == ")":
                depth += 1
            elif value[pos] == "(":
                depth -= 1
                if depth == 0:
                    opening = pos
                    break
        if opening <= 0:
            break
        body = value[opening + 1:-1].strip()
        # Function calls and arithmetic groups belong to the value. Qualifiers
        # describe the value and normally contain a key, selector or flag.
        if ":" not in body and not re.match(r"^(?:unless|if_|per_|next_|source_)", body):
            break
        qualifiers.insert(0, body)
        value = value[:opening].strip()
    return value, tuple(qualifiers)


def _parse_clause(raw, offset=0, parent_scope=()):
    leading = len(raw) - len(raw.lstrip())
    text = raw.strip()
    start = offset + leading
    end = start + len(text)
    if not text:
        return None

    pos, operator = _top_operator(text)
    head = text if pos < 0 else text[:pos].strip()
    scope = parent_scope
    if "." in head:
        bits = tuple(bit for bit in head.split(".") if bit)
        if not bits:
            # A head made only of dots ("...", ".") has no identifier to
            # anchor the clause. Refuse it explicitly so the failure surfaces
            # as a ParseError (caught upstream) instead of an IndexError that
            # would escape parse_tag/evaluate_tags and crash derive().
            raise ParseError("empty head at %d" % start)
        head = bits[-1]
        scope = parent_scope + bits[:-1]

    match = _IDENT.match(head)
    if match:
        name = match.group(0).lower()
    else:
        # Expressions such as if(...) and match(...) are structural nodes. Keep
        # their leading identifier so consumers can record them without losing
        # the original expression.
        match = re.match(r"([a-z_][a-z0-9_]*)", head, re.I)
        name = match.group(1).lower() if match else None
    if name is None:
        # Literals such as ``1/long_rest`` are valid structural operands in
        # legacy content. They remain explicit AST nodes and are ignored by
        # dispatch unless the library gives them semantics.
        return TagNode(name="_literal", operator="literal", value=text,
                       scope=scope, raw=text, start=start, end=end)

    if operator == "block":
        close = _matching(text, pos)
        if close < 0:
            raise ParseError("unclosed block at %d" % (start + pos))
        body = text[pos + 1:close]
        children = []
        child_scope = scope + (name,)
        for a, _b, part in _split_top(body):
            node = _parse_clause(part, start + pos + 1 + a, child_scope)
            if node is not None:
                children.append(node)
        suffix = text[close + 1:].strip()
        qualifiers = (suffix,) if suffix else ()
        return TagNode(name=name, operator="block", children=tuple(children),
                       qualifiers=qualifiers, scope=scope, raw=text,
                       start=start, end=end)

    value = None
    qualifiers = ()
    if operator != "flag":
        step = 2 if operator == ":=" else 1
        value, qualifiers = _strip_qualifiers(text[pos + step:])
    return TagNode(name=name, operator=operator, value=value,
                   qualifiers=qualifiers, scope=scope, raw=text,
                   start=start, end=end)


def parse_tag(text):
    text = str(text or "")
    errors = check_balance(tokenize(text), text)
    if errors:
        raise ParseError("; ".join(msg for _pos, msg in errors))
    nodes = []
    for start, _end, part in _split_top(text):
        node = _parse_clause(part, start)
        if node is not None:
            nodes.append(node)
    return TagProgram(nodes=tuple(nodes), source=text)


def parse_tags(tags):
    nodes = []
    source = []
    for tag in tags or ():
        program = parse_tag(tag)
        nodes.extend(program.nodes)
        source.append(program.source)
    return TagProgram(nodes=tuple(nodes), source="\n".join(source))
