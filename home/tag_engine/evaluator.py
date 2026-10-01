"""Library-driven evaluator for the Bonfire tag language.

Primitives select a small operation through tag_library.json. The evaluator
never branches on a feature, class or primitive name. New vocabulary using an
existing operation and target is executable without a backend code change.
"""
import ast
import math
import operator
import re
import unicodedata

from .library import Library
from .nodes import EvaluationResult, Operation
from .parser import parse_tags


_ARITHMETIC = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_COMPARISONS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_FUNCTIONS = {
    "abs": abs,
    "max": max,
    "min": min,
    "round": round,
    "rounddown": math.floor,
    "roundup": math.ceil,
}
_RUNTIME_SCOPES = {
    "aoe", "aura", "cast", "define", "effects", "else", "if", "instant",
    "list", "mark", "match", "on", "on_fail", "on_success", "pick", "save",
    "scaling", "table", "trigger", "upcast", "while", "while_active",
}


def _eval_ast(node, context):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in context:
        return context[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
        return _ARITHMETIC[type(node.op)](
            _eval_ast(node.left, context), _eval_ast(node.right, context))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ARITHMETIC:
        return _ARITHMETIC[type(node.op)](_eval_ast(node.operand, context))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_ast(node.operand, context)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        values = [_eval_ast(value, context) for value in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left, context)
        for comparison, comparator in zip(node.ops, node.comparators):
            fn = _COMPARISONS.get(type(comparison))
            if fn is None:
                raise ValueError("unsupported comparison")
            right = _eval_ast(comparator, context)
            if not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _FUNCTIONS.get(node.func.id)
        if fn is not None:
            return fn(*[_eval_ast(arg, context) for arg in node.args])
    raise ValueError("unsupported formula")


def evaluate_formula(value, context=None):
    text = str(value or "").strip()
    text = re.sub(r"\s*ft\s*$", "", text)
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if not text or re.search(r"\d+d\d+", text, re.I):
        return value
    try:
        result = _eval_ast(ast.parse(text, mode="eval").body, context or {})
        return int(result) if isinstance(result, float) and result.is_integer() else result
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError):
        return value


def _path_get(root, path, default=None):
    cur = root
    for part in [p for p in path.split(".") if p]:
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _path_set(root, path, value):
    parts = [p for p in path.split(".") if p]
    cur = root
    for part in parts[:-1]:
        existing = cur.get(part)
        if not isinstance(existing, dict):
            existing = ({"_value": existing} if existing is not None else {})
            cur[part] = existing
        cur = existing
    if parts:
        existing = cur.get(parts[-1])
        if isinstance(existing, dict):
            existing["_value"] = value
        else:
            cur[parts[-1]] = value


def _append_unique(root, path, value):
    current = _path_get(root, path)
    if isinstance(current, dict):
        current = current.setdefault("_values", [])
    elif current is not None and not isinstance(current, list):
        wrapper = {"_value": current, "_values": []}
        _path_set(root, path, wrapper)
        current = wrapper["_values"]
    if not isinstance(current, list):
        current = []
        _path_set(root, path, current)
    if value not in current:
        current.append(value)


def _operand(node, context):
    value = node.value
    if node.operator == "block":
        value = [child.raw for child in node.children]
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("+"):
            value = value[1:].strip()
        value = evaluate_formula(value, context)
    return value


def _split_balanced(text, separator=","):
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
        elif not stack and char == separator:
            parts.append(text[start:pos].strip())
            start = pos + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _top_binding(text):
    stack = []
    pairs = {"{": "}", "(": ")", "[": "]"}
    for pos, char in enumerate(text):
        if char in pairs:
            stack.append(pairs[char])
            continue
        if char in "}])":
            if stack and char == stack[-1]:
                stack.pop()
            continue
        if stack:
            continue
        if text.startswith(":=", pos):
            return pos, ":="
        if char == "=" and (
                pos == 0 or text[pos - 1] not in "<>!=") and (
                pos + 1 >= len(text) or text[pos + 1] != "="):
            return pos, "="
        if char == ":":
            return pos, ":"
    return -1, None


def _argument_parts(values, context, identifiers_are_flags=True):
    args, kwargs, raw_kwargs, flags = [], {}, {}, []
    for item in values:
        pos, operator_name = _top_binding(item)
        if pos > 0:
            key = item[:pos].strip()
            step = 2 if operator_name == ":=" else 1
            raw_value = item[pos + step:].strip()
            raw_kwargs[key] = raw_value
            kwargs[key] = evaluate_formula(raw_value.lstrip("+"), context)
        elif identifiers_are_flags and re.fullmatch(
                r"[a-z_][a-z0-9_]*", item, re.I):
            flags.append(item.lower())
        else:
            args.append(evaluate_formula(item.lstrip("+"), context))
    return args, kwargs, raw_kwargs, flags


def _operand_params(node, value, context):
    """Return a vocabulary-neutral structure for an operation operand.

    The parser owns scope; this layer only decomposes the operand grammar.
    Consumers can therefore dispatch by ``(op, target)`` and inspect data
    without reparsing primitive-specific strings.
    """
    raw = "" if node.value is None else str(node.value).strip()
    params = {
        "raw": raw,
        "name": None,
        "args": [],
        "kwargs": {},
        "raw_kwargs": {},
        "flags": [],
        "binding": None,
    }
    if not raw:
        return params

    pos, operator_name = _top_binding(raw)
    if pos > 0:
        params["name"] = raw[:pos].strip()
        step = 2 if operator_name == ":=" else 1
        rhs = raw[pos + step:].strip()
        params["binding"] = {
            "operator": operator_name,
            "raw": rhs,
            "value": evaluate_formula(rhs.lstrip("+"), context),
        }
        return params

    container = re.fullmatch(
        r"([a-z_][a-z0-9_.]*)\s*([\{\(])(.*)([\}\)])", raw, re.I)
    if container:
        opening, closing = container.group(2), container.group(4)
        if (opening, closing) in {("{", "}"), ("(", ")")}:
            params["name"] = container.group(1)
            values = _split_balanced(container.group(3))
            args, kwargs, raw_kwargs, flags = _argument_parts(
                values, context, identifiers_are_flags=False)
            params["args"], params["kwargs"], params["raw_kwargs"], params["flags"] = (
                args, kwargs, raw_kwargs, flags)
    elif re.fullmatch(r"[a-z_][a-z0-9_.]*", raw, re.I):
        params["name"] = raw

    qualifier_values = []
    for qualifier in node.qualifiers:
        qualifier_values.extend(_split_balanced(qualifier))
    args, kwargs, raw_kwargs, flags = _argument_parts(
        qualifier_values, context)
    params["args"].extend(args)
    params["kwargs"].update(kwargs)
    params["raw_kwargs"].update(raw_kwargs)
    params["flags"].extend(flag for flag in flags
                           if flag not in params["flags"])
    return params


def _condition_facts(context):
    """Normalize runtime condition facts into ``{condition: {sources}}``.

    Consumers may provide a set of names, a mapping of condition to source(s),
    or records such as ``{"name": "amedrontado", "source": "self"}``.
    An empty source set means that only the condition itself is known.
    """
    facts = {}
    source = context.get("conditions")
    if isinstance(source, dict):
        for name, relations in source.items():
            if isinstance(relations, str):
                relations = {relations}
            elif relations is None or relations is True:
                relations = set()
            else:
                relations = set(relations)
            facts[str(name).lower()] = {str(value).lower() for value in relations}
        return facts
    for item in source or ():
        if isinstance(item, dict):
            name = item.get("name") or item.get("condition")
            relation = item.get("source")
        else:
            name, relation = item, None
        if name:
            facts.setdefault(str(name).lower(), set())
            if relation:
                facts[str(name).lower()].add(str(relation).lower())
    return facts


def _equipment_truth(text, context):
    if "equiped" not in text and "equipped" not in text:
        return None
    equipped = set(context.get("equipped") or ())
    aliases = {
        "armadura": "armor", "armor": "armor",
        "armadura_pesada": "heavy_armor", "heavy_armor": "heavy_armor",
        "escudo": "shield", "shield": "shield",
    }
    matches = re.findall(r"equip(?:p)?ed\s*\{\s*([^{}]+)\}", text)
    if not matches:
        return None
    requested = {
        aliases.get(value, value)
        for arguments in matches
        for value in re.findall(r"[a-z_][a-z0-9_]*", arguments)
    }
    normalized = {aliases.get(str(value).lower(), str(value).lower())
                  for value in equipped}
    return bool(requested & normalized)


_SIZE_ORDER = ("miudo", "pequeno", "medio", "grande", "enorme", "descomunal")
_SIZE_ALIASES = dict(zip(
    ("tiny", "small", "medium", "large", "huge", "gargantuan"),
    _SIZE_ORDER,
))
_SIZE_ALIASES.update({"minimo": "miudo", "colossal": "descomunal",
                      "m": "medio", "l": "grande"})


def _target_size_truth(text, context):
    """Resolve a size gate only when a concrete target size is supplied."""
    match = re.fullmatch(
        r"target\s*\{\s*size\s*(<=|>=|=|<|>)\s*([a-z_]+)\s*\}", text)
    if not match:
        return None
    actual = context.get("target_size")
    if not isinstance(actual, str):
        return None
    actual = unicodedata.normalize("NFKD", actual).encode("ascii", "ignore").decode().lower()
    actual = _SIZE_ALIASES.get(actual, actual)
    expected = _SIZE_ALIASES.get(match.group(2), match.group(2))
    if actual not in _SIZE_ORDER or expected not in _SIZE_ORDER:
        return None
    compare = {"<": operator.lt, "<=": operator.le, "=": operator.eq,
               ">=": operator.ge, ">": operator.gt}[match.group(1)]
    return compare(_SIZE_ORDER.index(actual), _SIZE_ORDER.index(expected))


def _combat_fact_truth(text, context):
    """Resolve only combat facts explicitly supplied by the caller."""
    if text == "self{sangrando}":
        hp, maximum = context.get("self_hp"), context.get("self_max_hp")
        if isinstance(hp, (int, float)) and isinstance(maximum, (int, float)) and maximum > 0:
            return hp <= maximum / 2
        return None
    if text == "target{hp<max_hp}":
        hp, maximum = context.get("target_hp"), context.get("target_max_hp")
        if isinstance(hp, (int, float)) and isinstance(maximum, (int, float)) and maximum > 0:
            return hp < maximum
        return None
    if text == "target{in:self_space}":
        value = context.get("target_in_self_space")
        return value if isinstance(value, bool) else None
    return None


def _condition_truth(text, context):
    match = re.search(
        r"condition\s*\{\s*([a-z0-9_]+)([^{}]*)\}",
        text,
    )
    if match:
        facts = _condition_facts(context)
        name, arguments = match.group(1), match.group(2)
        source_match = re.search(
            r"\bsource\s*:\s*([a-z0-9_]+)", arguments)
        target_match = re.search(
            r"\btarget\s*:\s*([a-z0-9_]+)", arguments)
        source = source_match.group(1) if source_match else None
        target = target_match.group(1) if target_match else None
        if target and target != "self":
            return None
        if name not in facts:
            return False if "conditions" in context else None
        return not source or not facts[name] or source in facts[name]

    # A catalog condition may also be used directly: restriction{inconsciente}.
    facts = _condition_facts(context)
    if not facts:
        return False if "conditions" in context else None
    words = re.findall(r"\b[a-z_][a-z0-9_]*\b", text)
    matches = [word for word in words if word in facts]
    return bool(matches) if matches else False


def _unwrap_outer_block(text, name):
    text = text.strip()
    colon_prefix = name + ":"
    if text.startswith(colon_prefix):
        return text[len(colon_prefix):].strip()
    block_prefix = name + "{"
    if not text.startswith(block_prefix) or not text.endswith("}"):
        return text
    start = len(name)
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                if pos == len(text) - 1:
                    return text[start + 1:pos].strip()
                break
    return text


def _predicate_text_truth(text, context):
    text = str(text or "").lower().strip()
    text = _unwrap_outer_block(text, "requires")
    text = _unwrap_outer_block(text, "restriction")

    negated = _unwrap_outer_block(text, "not")
    if negated != text:
        truth = _predicate_text_truth(negated, context)
        return None if truth is None else not truth

    combat_fact = _combat_fact_truth(text, context)
    if combat_fact is not None:
        return combat_fact

    target_size = _target_size_truth(text, context)
    if target_size is not None:
        return target_size

    equipment = _equipment_truth(text, context)
    if equipment is not None:
        return equipment

    condition = _condition_truth(text, context)
    if condition is not None:
        return condition

    level = int(context.get("lvl") or 0)
    match = re.search(r"\blvl\s*(?:(?:>=|=)\s*|\{\s*)(\d+)", text)
    if match:
        return level >= int(match.group(1))

    match = re.fullmatch(r"(?:requires\s*:)?\s*([a-z_][a-z0-9_]*)", text)
    if match and match.group(1) in context:
        return bool(context[match.group(1)])
    return None


def _predicate_truth(node, context):
    """Evaluate a gate predicate when the supplied context makes it decidable.

    ``None`` means runtime/unknown. This is deliberately vocabulary-agnostic:
    condition names and equipment identifiers are operands, never code paths.
    """
    return _predicate_text_truth(node.raw, context)


def _gate_blocks(node, context):
    truth = _predicate_truth(node, context)
    if truth is None:
        return False
    if node.name == "restriction":
        return truth
    if node.name == "requires":
        return not truth
    return False


class Evaluator:
    def __init__(self, library=None):
        self.library = library or Library()

    def _spec(self, verb):
        value = (self.library.raw.get("primitives") or {}).get(verb)
        if value is None:
            value = (self.library.raw.get("tags_de_classe") or {}).get(verb)
        return value if isinstance(value, dict) else None

    def _operation(self, node, context, active):
        spec = self._spec(node.name)
        if not spec or not spec.get("op"):
            return None
        op = spec["op"]
        raw_operand = "" if node.value is None else str(node.value).strip()
        if (op == "set_value" and node.operator == ":"
                and raw_operand.startswith(("+", "-"))):
            op = "add_modifier"
        target = spec.get("target") or "operations.%s" % op
        operand = _operand(node, context)
        value_spec = spec.get("value") or {}
        return Operation(
            op=op,
            target=target,
            value=operand,
            verb=node.name,
            scope=node.scope,
            qualifiers=node.qualifiers,
            raw=node.raw,
            params=_operand_params(node, operand, context),
            value_type=(value_spec.get("type", "")
                        if isinstance(value_spec, dict) else ""),
            active=active,
        )

    def _dispatch(self, state, operation):
        if not operation.active:
            _append_unique(state, "runtime", operation)
            return
        op = operation.op
        target = operation.target
        if op in {"add_to_set", "grant_proficiency", "grant_roll_mod"}:
            _append_unique(state, target, operation.value)
        elif op in {"add_modifier", "add_damage", "alter_attribute"}:
            _append_unique(state, target, {
                "value": operation.value,
                "scope": operation.scope,
                "qualifiers": operation.qualifiers,
                "verb": operation.verb,
            })
        elif op == "set_value":
            _path_set(state, target, operation.value)
        elif op == "set_property":
            name = operation.params.get("name")
            binding = operation.params.get("binding") or {}
            if name and "value" in binding:
                _path_set(state, "%s.%s" % (target, name), binding["value"])
        elif op == "gate":
            _append_unique(state, "gates", operation.raw)
        elif op == "restrict":
            _append_unique(state, "restrictions", operation.value)
        elif op == "meta":
            _append_unique(state, "meta", operation.raw)
        else:
            _append_unique(state, target, {
                "op": operation.op,
                "value": operation.value,
                "scope": operation.scope,
                "qualifiers": operation.qualifiers,
                "verb": operation.verb,
            })

    def _walk_scope(self, nodes, state, operations, context, active=True):
        # Static inspection remains the default. Callers resolving one combat
        # event opt in with explicit facts; unknown facts never activate a gate.
        resolve_runtime = context.get("resolve_runtime") is True
        attack_action = resolve_runtime and any(node.name == "attack" for node in nodes)
        gates = [node for node in nodes
                 if node.name in {"restriction", "requires"}]
        blockers = [gate.raw for gate in gates if _gate_blocks(gate, context)]
        if resolve_runtime:
            blockers.extend(gate.raw for gate in gates
                            if gate.name == "requires" and
                            _predicate_truth(gate, context) is None)
            for trigger in (node for node in nodes if node.name == "trigger"):
                event = context.get("event")
                if not isinstance(event, str) or trigger.value != event:
                    blockers.append(trigger.raw)
        if blockers:
            return blockers

        previous_if = None
        for node in nodes:
            if node.name in {"restriction", "requires"}:
                operation = self._operation(node, context, active)
                if operation:
                    operations.append(operation)
                    self._dispatch(state, operation)
                continue

            child_active = active
            if resolve_runtime and node.name in {"if", "else"}:
                if node.name == "if":
                    opening = node.raw.find("(")
                    depth = 0
                    closing = None
                    for pos in range(opening, len(node.raw)):
                        if node.raw[pos] == "(":
                            depth += 1
                        elif node.raw[pos] == ")":
                            depth -= 1
                            if depth == 0:
                                closing = pos
                                break
                    previous_if = (_predicate_text_truth(
                        node.raw[opening + 1:closing], context)
                        if opening >= 0 and closing is not None else None)
                    child_active = active and previous_if is True
                else:
                    child_active = active and previous_if is False
                    previous_if = None
            elif resolve_runtime and node.name in {"instant", "while_active"}:
                child_active = active
            elif node.name in _RUNTIME_SCOPES:
                child_active = False
            elif node.name == "always_active":
                child_active = active

            if resolve_runtime and node.value and "{requires:" in str(node.value):
                operand = str(node.value)
                qualifier = operand[operand.find("{requires:") + 1:-1]
                if operand.endswith("}") and _predicate_text_truth(qualifier, context) is not True:
                    child_active = False
            if attack_action:
                event = context.get("event")
                if event == "attack":
                    if node.name not in {"attack", "reach", "adv", "while_active"}:
                        child_active = False
                elif event == "hit":
                    if node.name in {"attack", "reach", "adv"}:
                        child_active = False
                elif node.name != "while_active":
                    child_active = False

            operation_active = child_active
            if (resolve_runtime and node.name == "instant" and not node.scope and
                    any(child.name == "attack" for child in node.children) and
                    context.get("event") != "attack"):
                operation_active = False
            operation = self._operation(node, context, operation_active)
            if operation:
                operations.append(operation)
                self._dispatch(state, operation)

            if node.children:
                nested = self._walk_scope(
                    node.children, state, operations, context, child_active)
                for blocker in nested:
                    _append_unique(state, "blocked_scopes", {
                        "scope": node.path,
                        "gate": blocker,
                    })
        return []

    def evaluate(self, tags, context=None):
        context = dict(context or {})
        program = parse_tags(tags)
        state = {}
        operations = []
        blockers = self._walk_scope(
            program.nodes, state, operations, context, active=True)
        return EvaluationResult(
            state=state,
            operations=operations,
            blocked=bool(blockers),
            blocked_by=blockers,
        )


def evaluate_tags(tags, context=None, library=None):
    return Evaluator(library=library).evaluate(tags, context=context)
