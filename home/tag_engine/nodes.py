"""AST nodes for the Bonfire tag language.

The AST keeps source order and lexical scope. Runtime consumers can therefore
distinguish a gate on the whole ability from a gate nested in one effect block.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class TagNode:
    name: str
    operator: str = "flag"
    value: Any = None
    children: Tuple["TagNode", ...] = field(default_factory=tuple)
    qualifiers: Tuple[str, ...] = field(default_factory=tuple)
    scope: Tuple[str, ...] = field(default_factory=tuple)
    raw: str = ""
    start: int = 0
    end: int = 0

    @property
    def path(self) -> str:
        return ".".join(self.scope + (self.name,))


@dataclass(frozen=True)
class TagProgram:
    nodes: Tuple[TagNode, ...]
    source: str = ""


@dataclass
class Operation:
    op: str
    target: str
    value: Any
    verb: str
    scope: Tuple[str, ...]
    qualifiers: Tuple[str, ...]
    raw: str
    params: dict = field(default_factory=dict)
    value_type: str = ""
    active: bool = True
    blocked_by: Optional[str] = None


@dataclass
class EvaluationResult:
    state: dict
    operations: List[Operation]
    blocked: bool = False
    blocked_by: List[str] = field(default_factory=list)
