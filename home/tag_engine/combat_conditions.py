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
    expires_at_target_turn: int


class CombatConditions:
    def __init__(self):
        self._turns = {}
        self._turn_ids = {}
        self._conditions = set()

    def start_turn(self, actor, turn_id):
        """Expire effects at the start of this actor's next distinct turn."""
        if not actor or turn_id is None:
            raise ValueError("actor and turn_id are required")
        if self._turn_ids.get(actor) == turn_id:
            return
        self._turn_ids[actor] = turn_id
        self._turns[actor] = self._turns.get(actor, 0) + 1
        self._conditions = {
            effect for effect in self._conditions
            if effect.target != actor or
            effect.expires_at_target_turn > self._turns[actor]
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
            duration = operation.params.get("kwargs", {}).get("duration")
            if duration != "until_turn_start":
                continue
            name = operation.params.get("name")
            if name:
                self._conditions.add(ActiveCondition(
                    name=name.lower(), source=source, target=target,
                    expires_at_target_turn=self._turns.get(target, 0) + 1,
                ))
        return result
