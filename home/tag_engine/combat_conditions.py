"""Turn-scoped condition facts for consumers of the tag evaluator.

This is an in-memory combat event projection. The caller owns the encounter,
actor identities and turn sequence; no character or bestiary row is mutated.
"""
from dataclasses import dataclass

from .evaluator import evaluate_tags


@dataclass(frozen=True)
class ActiveCondition:
    name: str
    source: str
    target: str
    expires_on_actor: str
    expires_at_turn: int
    source_tags: tuple[str, ...] = ()


class CombatConditions:
    def __init__(self):
        self._turns = {}
        self._seen_turn_ids = {}
        self._conditions = set()

    def start_turn(self, actor, turn_id):
        """Expire effects at the start of this actor's next distinct turn."""
        if not actor or turn_id is None:
            raise ValueError("actor and turn_id are required")
        seen = self._seen_turn_ids.setdefault(actor, set())
        if turn_id in seen:
            return False
        seen.add(turn_id)
        self._turns[actor] = self._turns.get(actor, 0) + 1
        self._conditions = {
            effect for effect in self._conditions
            if effect.expires_on_actor != actor or
            effect.expires_at_turn > self._turns[actor]
        }
        return True

    def facts(self, target, source):
        """Return source-relative facts without granting credit to other sources."""
        if not target or not source:
            raise ValueError("source and target are required")
        facts = {}
        for effect in self._conditions:
            if effect.target == target:
                facts.setdefault(effect.name, set()).add(
                    "self" if effect.source == source else "other")
        return facts

    def remove(self, target, name, source):
        """End one source's condition; other grapplers remain active."""
        if not target or not name or not source:
            raise ValueError("target, condition and source are required")
        remaining = {
            effect for effect in self._conditions
            if (effect.target != target or effect.name != name or
                effect.source != source)
        }
        removed = len(self._conditions) - len(remaining)
        self._conditions = remaining
        return removed

    def blocks_healing(self, target):
        """Evaluate restrictions from the action that applied each active effect."""
        for effect in self._conditions:
            if effect.target != target or not effect.source_tags:
                continue
            result = evaluate_tags(effect.source_tags, {
                "resolve_runtime": True,
                "event": "healing",
                "conditions": self.facts(target, effect.source),
            })
            if any(operation.active and operation.op == "restrict" and
                   isinstance(operation.value, list) and
                   "heal" in operation.value and "target" in operation.value
                   for operation in result.operations):
                return True
        return False

    def resolve(self, tags, *, event, source, target, context=None):
        """Evaluate one event and retain supported condition applications."""
        tags = tuple(tags)
        facts = dict(context or {})
        facts.update(resolve_runtime=True, event=event,
                     conditions=self.facts(target, source))
        result = evaluate_tags(tags, facts)
        for operation in result.operations:
            if not operation.active or operation.op != "apply_condition":
                continue
            params = operation.params
            kwargs = params.get("kwargs", {})
            duration = kwargs.get("duration")
            if duration not in {"until_turn_start", "until_source_turn_start"}:
                continue
            recipient = kwargs.get("target")
            args = params.get("args", [])
            if recipient is None:
                flags = params.get("flags", [])
                recipient = ("self" if "self" in flags else
                             "target" if "target" in flags else
                             args[0] if args else None)
            if recipient == "self":
                condition_target = source
            elif recipient in (None, "target", "active", "hit"):
                condition_target = target
            else:
                # A selector such as an area or ally needs a resolved actor ID.
                continue
            name = params.get("name")
            if name:
                expiry_actor = (source if duration == "until_source_turn_start"
                                else condition_target)
                self._conditions.add(ActiveCondition(
                    name=name.lower(), source=source, target=condition_target,
                    expires_on_actor=expiry_actor,
                    expires_at_turn=self._turns.get(expiry_actor, 0) + 1,
                    source_tags=tags,
                ))
        return result
