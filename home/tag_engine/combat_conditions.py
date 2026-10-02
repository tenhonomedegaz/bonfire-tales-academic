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
            return
        seen.add(turn_id)
        self._turns[actor] = self._turns.get(actor, 0) + 1
        self._conditions = {
            effect for effect in self._conditions
            if effect.expires_on_actor != actor or
            effect.expires_at_turn > self._turns[actor]
        }

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

    def resolve(self, tags, *, event, source, target, context=None):
        """Evaluate one event and retain supported condition applications."""
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
                ))
        return result
