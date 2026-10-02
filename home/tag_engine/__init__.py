# -*- coding: utf-8 -*-
"""Motor interpretador das tags_json do Bonfire Tales.

Lê a especificação `home/tag_library.json` (NADA hardcoded) e valida cada
tag como o Excel valida uma fórmula: aponta exatamente onde a fórmula está
errada (delimitador aberto, verbo desconhecido, referência inexistente,
valor fora do catálogo).

Uso programático:
    from home.tag_engine import Library, validate_tags_json, DataIndex
    lib = Library()
    diags = validate_tags_json(tags_list, lib)           # só sintaxe/vocabulário
    diags = validate_tags_json(tags_list, lib, DataIndex.build())  # + #REF!

Ou pela linha de comando:
    manage.py validate_tags                 # valida TODO o banco
    manage.py validate_tags --lint          # só audita a biblioteca
    manage.py validate_tags --model talento --errors-only
"""
from .library import Library
from .lexer import tokenize, LexError
from .nodes import EvaluationResult, Operation, TagNode, TagProgram
from .parser import ParseError, parse_tag, parse_tags
from .evaluator import Evaluator, evaluate_formula, evaluate_tags
from .combat_conditions import CombatConditions
from .combat_encounter import CombatEncounter
from .validator import (
    Diagnostic, DataIndex,
    normalize_tag_identifier_names,
    validate_tag_line, validate_tags_json,
    ERROR, WARN, INFO,
)

__all__ = [
    "Library", "tokenize", "LexError",
    "TagNode", "TagProgram", "Operation", "EvaluationResult",
    "ParseError", "parse_tag", "parse_tags",
    "Evaluator", "evaluate_formula", "evaluate_tags",
    "CombatConditions", "CombatEncounter",
    "Diagnostic", "DataIndex",
    "normalize_tag_identifier_names",
    "validate_tag_line", "validate_tags_json",
    "ERROR", "WARN", "INFO",
]
