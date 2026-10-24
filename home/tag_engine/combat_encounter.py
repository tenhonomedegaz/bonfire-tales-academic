"""In-memory encounter execution with declared hit and damage outcomes.

The table/VTT supplies dice outcomes and turn order. This executor owns HP,
action use, condition timing and healing restrictions for one encounter; it
does not persist characters or pretend to resolve every RPG combat rule.
"""

from .combat_conditions import CombatConditions
from .attack_effects import ignored_resistance_types, ignores_resistance
from .evaluator import evaluate_tags
from .parser import parse_tag


class CombatEncounter:
    def __init__(self, combatants):
        self._combatants = {}
        for entry in combatants:
            if not isinstance(entry, dict):
                raise ValueError("Invalid combatant")
            actor = entry.get("id")
            team = entry.get("team")
            maximum = entry.get("max_hp")
            hp = entry.get("hp", maximum)
            temp_hp = entry.get("temp_hp", 0)
            defensive_tags = entry.get("defensive_tags", entry.get("tags", ()))
            offensive_tags = entry.get("offensive_tags", entry.get("tags", ()))
            tag_context = entry.get("tag_context", {})
            if (not isinstance(actor, str) or not actor or actor in self._combatants or
                    not isinstance(team, str) or not team or
                    type(maximum) is not int or maximum <= 0 or
                    type(hp) is not int or not 0 < hp <= maximum or
                    type(temp_hp) is not int or temp_hp < 0 or
                    isinstance(defensive_tags, str) or
                    isinstance(offensive_tags, str) or not isinstance(tag_context, dict)):
                raise ValueError("Invalid combatant")
            try:
                defensive_tags = tuple(defensive_tags)
                offensive_tags = tuple(offensive_tags)
            except TypeError as error:
                raise ValueError("Invalid combatant") from error
            if not all(isinstance(tag, str) for tag in defensive_tags + offensive_tags):
                raise ValueError("Invalid combatant")
            self._combatants[actor] = {
                "team": team, "max_hp": maximum, "hp": hp,
                "temp_hp": temp_hp,
                "defensive_tags": defensive_tags,
                "offensive_tags": offensive_tags,
                "tag_context": dict(tag_context),
            }
        if len({entry["team"] for entry in self._combatants.values()}) < 2:
            raise ValueError("An encounter needs at least two teams")
        self.conditions = CombatConditions()
        self.current_actor = None
        self.action_used = False
        self.finished = False
        self._events = []
        self._healing_tag_uses = set()
        self._fall_progress = {}

    @property
    def combatants(self):
        return {
            actor: {key: value for key, value in entry.items()
                    if key not in {"defensive_tags", "offensive_tags", "tag_context"}}
            for actor, entry in self._combatants.items()
        }

    @property
    def events(self):
        return tuple(self._events)

    def _living(self, actor):
        if actor not in self._combatants or self._combatants[actor]["hp"] == 0:
            raise ValueError("Actor is not active in this encounter")

    def _action_actor(self):
        if self.finished or self.current_actor is None or self.action_used:
            raise ValueError("No action is available")
        return self.current_actor

    def start_turn(self, actor, turn_id):
        if self.finished or self.current_actor is not None:
            raise ValueError("Finish the current turn first")
        self._living(actor)
        if not self.conditions.start_turn(actor, turn_id):
            return False
        self._healing_tag_uses = {
            key for key in self._healing_tag_uses if key[0] != actor
        }
        self.current_actor = actor
        self.action_used = False
        self._events.append(("turn_start", actor, turn_id))
        return True

    def fall(self, actor, remaining_distance_ft, *, turn_id):
        """Resolve the distance fallen this turn from the actor's movement tags.

        The table supplies the remaining distance and turn identity. Multiple
        calls in one turn share the same limit, including falls outside the
        actor's own turn.
        """
        if (actor not in self._combatants or type(remaining_distance_ft) is not int
                or remaining_distance_ft < 0 or
                not isinstance(turn_id, (str, int)) or not str(turn_id)):
            raise ValueError("Declare an actor, distance and turn")
        from home.epic_sky_runtime import consume_movement_operation

        entry = self._combatants[actor]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="fall",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        properties, rule = {}, {}
        for operation in evaluate_tags(entry["defensive_tags"], context).operations:
            if operation.active:
                consume_movement_operation(operation, properties, rule)

        actual = remaining_distance_ft
        threshold = rule.get("threshold_ft")
        speed = rule.get("max_per_turn_ft")
        if threshold is not None and speed is not None:
            turn_key = str(turn_id)
            previous_turn, used = self._fall_progress.get(actor, (None, 0))
            if previous_turn != turn_key:
                used = 0
            if remaining_distance_ft > threshold:
                actual = min(remaining_distance_ft, max(0, speed - used))
            self._fall_progress[actor] = (turn_key, used + actual)
        self._events.append(("fall", actor, turn_id, remaining_distance_ft, actual))
        return actual

    def _damage_after_defenses(self, target, damage, damage_type, ignored=()):
        """Apply target-declared resistance or immunity for one typed hit."""
        if damage_type is None:
            return damage
        target_entry = self._combatants[target]
        context = dict(target_entry["tag_context"])
        context.update({
            "resolve_runtime": True,
            "event": "take_damage",
            "self_hp": target_entry["hp"],
            "self_max_hp": target_entry["max_hp"],
        })
        result = evaluate_tags(target_entry["defensive_tags"], context)
        defenses = {
            operation.target
            for operation in result.operations
            if operation.active and operation.op == "add_to_set" and
            operation.target in {"resistencias", "imunidades"} and
            operation.value == damage_type
        }
        if "imunidades" in defenses:
            return 0
        if "resistencias" in defenses and not ignores_resistance(ignored, damage_type):
            return damage // 2
        return damage

    def attack(self, target, tags, *, hit, damage=0, damage_type=None):
        source = self._action_actor()
        self._living(target)
        tags = tuple(tags)
        if (type(hit) is not bool or type(damage) is not int or damage < 0 or
                (damage_type is not None and
                 (not isinstance(damage_type, str) or not damage_type.strip())) or
                (not hit and damage)):
            raise ValueError("Declare a valid hit and rolled damage")
        operations = None
        if hit:
            source_entry = self._combatants[source]
            attack_context = dict(source_entry["tag_context"])
            attack_context.update(resolve_runtime=True, event="hit",
                                  self_hp=source_entry["hp"],
                                  self_max_hp=source_entry["max_hp"])
            attack_effects = evaluate_tags(
                source_entry["offensive_tags"] + tags, attack_context)
            ignored = ignored_resistance_types(attack_effects.operations)
            operations = self.conditions.resolve(
                tags, event="hit", source=source, target=target)
            damage = self._damage_after_defenses(
                target, damage, damage_type.strip().lower()
                if isinstance(damage_type, str) else None, ignored)
            target_entry = self._combatants[target]
            absorbed = min(target_entry["temp_hp"], damage)
            target_entry["temp_hp"] -= absorbed
            target_entry["hp"] = max(0, target_entry["hp"] - (damage - absorbed))
        self.action_used = True
        self._events.append(("attack", source, target, hit, damage))
        self._finish_if_decided()
        return operations

    def heal(self, target, amount):
        source = self._action_actor()
        self._living(target)
        if type(amount) is not int or amount < 0:
            raise ValueError("Declare a nonnegative healing amount")
        blocked = self.conditions.blocks_healing(target)
        if not blocked:
            entry = self._combatants[target]
            bonus = (self._healing_tag_bonus(target)
                     if amount and entry["hp"] < entry["max_hp"] else 0)
            entry["hp"] = min(entry["max_hp"], entry["hp"] + amount + bonus)
        self.action_used = True
        self._events.append(("heal", source, target, amount, blocked))
        return not blocked

    def grant_temporary_hp(self, target, amount):
        """Grant temporary HP after resolving the target's generic modifiers.

        Temporary HP replaces an existing lower value, following the normal
        replacement rule. It is intentionally a separate encounter action
        from healing: temporary HP is not healing and does not check healing
        restrictions.
        """
        source = self._action_actor()
        self._living(target)
        if type(amount) is not int or amount < 0:
            raise ValueError("Declare a nonnegative temporary HP amount")
        entry = self._combatants[target]
        received = (amount + self._temporary_hp_tag_bonus(target)
                    if amount else 0)
        entry["temp_hp"] = max(entry["temp_hp"], received)
        self.action_used = True
        self._events.append(("temp_hp", source, target, amount, received))
        return received

    @staticmethod
    def _limited_per_turn(tag, scope):
        """Whether a ``1/turn`` literal governs this operation's AST scope."""
        program = parse_tag(tag)

        def walk(nodes):
            for node in nodes:
                if (node.name == "_literal" and
                        str(node.value).replace(" ", "") == "1/turn" and
                        tuple(scope[:len(node.scope)]) == node.scope):
                    return True
                if walk(node.children):
                    return True
            return False

        return walk(program.nodes)

    def _healing_tag_bonus(self, target):
        """Resolve target healing modifiers declared by generic runtime tags."""
        entry = self._combatants[target]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="healing",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        total = 0
        for tag_index, tag in enumerate(entry["defensive_tags"]):
            result = evaluate_tags((tag,), context)
            for operation_index, operation in enumerate(result.operations):
                if (not operation.active or operation.op != "heal" or
                        not isinstance(operation.value, (int, float))):
                    continue
                key = (target, tag_index, operation_index)
                if self._limited_per_turn(tag, operation.scope):
                    if key in self._healing_tag_uses:
                        continue
                    self._healing_tag_uses.add(key)
                total += max(0, int(operation.value))
        return total

    def _temporary_hp_tag_bonus(self, target):
        """Resolve generic modifiers to temporary HP received by a target."""
        entry = self._combatants[target]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="receive_temp_hp",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        total = 0
        for operation in evaluate_tags(entry["defensive_tags"], context).operations:
            if (operation.active and operation.op == "heal" and
                    operation.target == "pv_temporario" and
                    isinstance(operation.value, (int, float))):
                total += max(0, int(operation.value))
        return total

    def end_turn(self):
        if self.current_actor is None:
            raise ValueError("No turn to finish")
        self._events.append(("turn_end", self.current_actor))
        self.current_actor = None
        self.action_used = False

    def _finish_if_decided(self):
        living_teams = {
            entry["team"] for entry in self._combatants.values() if entry["hp"] > 0
        }
        if len(living_teams) == 1:
            self.finished = True
            self._events.append(("encounter_end", next(iter(living_teams))))
            self.current_actor = None
