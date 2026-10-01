"""Read-only target-size guidance for tagged bestiary actions."""

import re

from .tag_engine import evaluate_tags, parse_tags
from .tag_engine.parser import ParseError


TARGET_SIZE_OPTIONS = (
    ("miudo", "Mínimo"),
    ("pequeno", "Pequeno"),
    ("medio", "Médio"),
    ("grande", "Grande"),
    ("enorme", "Enorme"),
    ("descomunal", "Colossal"),
)
_SIZE_KEYS = {key for key, _label in TARGET_SIZE_OPTIONS}
_SIZE_GATE = re.compile(
    r"target\s*\{\s*size\s*(?:<=|>=|=|<|>)\s*[a-z_]+\s*\}", re.I)


def selected_target_size(raw):
    value = str(raw or "").strip().lower()
    return value if value in _SIZE_KEYS else None


def size_gate_note(tags, target_size):
    """Report gate applicability; do not treat a hit or saving throw as resolved."""
    if target_size not in _SIZE_KEYS or not tags:
        return ""
    try:
        program = parse_tags(tags)
    except (ParseError, ValueError, TypeError):
        return ""
    gates = []

    def visit(nodes):
        for node in nodes:
            if node.name == "requires" and _SIZE_GATE.fullmatch(str(node.value or "")):
                gates.append(node.raw)
            visit(node.children)

    visit(program.nodes)
    if not gates:
        return ""
    checks = [not evaluate_tags([gate], {"target_size": target_size}).blocked
              for gate in gates]
    return ("Limite de tamanho atendido; confira as demais condições da ação."
            if all(checks) else "Limite de tamanho não atendido por este alvo.")


def annotate_target_size(display, target_size):
    if target_size not in _SIZE_KEYS:
        return display
    for section in ("traits", "actions", "bonus", "reactions", "legendary", "mythic", "lair", "regional"):
        for block in display.get(section) or ():
            block["size_gate_note"] = size_gate_note(block.get("tags"), target_size)
    return display
