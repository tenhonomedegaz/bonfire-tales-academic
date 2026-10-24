"""In-memory encounter execution with declared hit and damage outcomes.

The table/VTT supplies dice outcomes and turn order. This executor owns HP,
action use, condition timing and healing restrictions for one encounter; it
does not persist characters or pretend to resolve every RPG combat rule.
"""

import re

from .combat_conditions import CombatConditions
from .attack_effects import (critical_damage_bonus, ignored_resistance_types,
                             ignores_resistance)
from .evaluator import evaluate_tags
from .parser import parse_tag


class CombatEncounter:
    def __init__(self, combatants):
        self._combatants = {}
        initial_concentration = {}
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
            concentration = entry.get("concentration")
            if (not isinstance(actor, str) or not actor or actor in self._combatants or
                    not isinstance(team, str) or not team or
                    type(maximum) is not int or maximum <= 0 or
                    type(hp) is not int or not 0 < hp <= maximum or
                    type(temp_hp) is not int or temp_hp < 0 or
                    isinstance(defensive_tags, str) or
                    isinstance(offensive_tags, str) or not isinstance(tag_context, dict) or
                    (concentration is not None and
                     (not isinstance(concentration, str) or
                      not 0 < len(concentration.strip()) <= 100))):
                raise ValueError("Invalid combatant")
            try:
                defensive_tags = tuple(defensive_tags)
                offensive_tags = tuple(offensive_tags)
            except TypeError as error:
                raise ValueError("Invalid combatant") from error
            if not all(isinstance(tag, str) for tag in defensive_tags + offensive_tags):
                raise ValueError("Invalid combatant")
            tag_context = dict(tag_context)
            tag_context.setdefault("in_dim_light", False)
            if type(tag_context["in_dim_light"]) is not bool:
                raise ValueError("Declare whether the combatant is in dim light or darkness")
            self._combatants[actor] = {
                "team": team, "max_hp": maximum, "hp": hp,
                "temp_hp": temp_hp,
                "defensive_tags": defensive_tags,
                "offensive_tags": offensive_tags,
                "tag_context": tag_context,
            }
            if concentration is not None:
                initial_concentration[actor] = concentration.strip()
        if len({entry["team"] for entry in self._combatants.values()}) < 2:
            raise ValueError("An encounter needs at least two teams")
        self.conditions = CombatConditions()
        self.current_actor = None
        self.action_used = False
        self.bonus_action_used = False
        self.finished = False
        self._events = []
        self._dodge_active = set()
        self._bonus_invisible = set()
        self._reactions_used = set()
        self._action_kind = None
        self._action_actor_id = None
        self._teleport_pending_kind = None
        self._teleport_used = False
        self._attack_reach_bonus = {}
        self._healing_tag_uses = set()
        self._fall_progress = {}
        self._concentration = initial_concentration
        self._concentration_save_pending = set()

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
        self.bonus_action_used = False
        self._action_kind = None
        self._action_actor_id = None
        self._teleport_pending_kind = None
        self._teleport_used = False
        self._dodge_active.discard(actor)
        self._reactions_used.discard(actor)
        self._attack_reach_bonus.pop(actor, None)
        self._events.append(("turn_start", actor, turn_id))
        return True

    def set_lighting(self, actor, *, in_dim_light):
        """Apply the table's current lighting fact to conditional tags."""
        self._living(actor)
        if type(in_dim_light) is not bool:
            raise ValueError("Lighting must be declared")
        self._combatants[actor]["tag_context"]["in_dim_light"] = in_dim_light
        self._events.append(("lighting", actor, in_dim_light))

    def invisibility_state(self, actor):
        """Project invisibility granted by this encounter's action tags."""
        if actor not in self._combatants:
            raise ValueError("Unknown combatant")
        return actor in self._bonus_invisible and self._combatants[actor]["hp"] > 0

    def _break_invisibility(self, actor):
        if actor in self._bonus_invisible:
            self._bonus_invisible.remove(actor)
            self._events.append(("invisibility_end", actor))

    def concentration_state(self, actor):
        if actor not in self._combatants:
            raise ValueError("Unknown combatant")
        return {"source": self._concentration.get(actor),
                "save_required": actor in self._concentration_save_pending}

    def begin_concentration(self, actor, source_ref):
        """Record a cast resolved by the table/VTT and replace prior focus."""
        self._living(actor)
        if self.finished or not isinstance(source_ref, str) or not 0 < len(source_ref.strip()) <= 100:
            raise ValueError("Declare a concentration source")
        source_ref = source_ref.strip()
        previous = self._concentration.get(actor)
        if previous == source_ref:
            return False
        self._concentration[actor] = source_ref
        self._concentration_save_pending.discard(actor)
        self._events.append(("concentration_start", actor, source_ref, previous))
        return True

    def resolve_concentration_event(self, actor, event, *, save_success=None):
        """Consume explicit hard breaks and table-declared damage saves."""
        if actor not in self._combatants or event not in {
                "damage", "petrified", "unconscious", "death"}:
            raise ValueError("Invalid concentration event")
        if save_success is not None and (event != "damage" or type(save_success) is not bool):
            raise ValueError("Declare a valid concentration save result")
        if actor not in self._concentration:
            return "inactive"
        if event != "damage":
            self._concentration.pop(actor)
            self._concentration_save_pending.discard(actor)
            outcome = "ended"
        else:
            entry = self._combatants[actor]
            context = dict(entry["tag_context"])
            context.update(resolve_runtime=True, event="take_damage",
                           self_hp=entry["hp"], self_max_hp=entry["max_hp"])
            focused = any(
                operation.active and operation.op == "suppress"
                and "concentration_break" in operation.value
                for tag in entry["defensive_tags"]
                for operation in evaluate_tags((tag,), context).operations
            )
            if focused:
                self._concentration_save_pending.discard(actor)
                outcome = "retained"
            elif save_success is None:
                self._concentration_save_pending.add(actor)
                outcome = "save_required"
            elif save_success:
                self._concentration_save_pending.discard(actor)
                outcome = "retained"
            else:
                self._concentration.pop(actor)
                self._concentration_save_pending.discard(actor)
                outcome = "ended"
        self._events.append(("concentration", actor, event, outcome))
        return outcome

    def bonus_action_invisibility(self):
        """Spend the current actor's bonus action when a light-gated tag grants it."""
        actor = self.current_actor
        if (self.finished or actor is None or self.bonus_action_used
                or self._teleport_pending_kind):
            raise ValueError("No bonus action is available")
        self._living(actor)
        if actor in self._bonus_invisible:
            raise ValueError("Already invisible from this source")
        entry = self._combatants[actor]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="bonus_action",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        tags = entry["defensive_tags"] + tuple(
            tag for tag in entry["offensive_tags"]
            if tag not in entry["defensive_tags"])
        granted = any(
            operation.active and operation.op == "apply_condition"
            and operation.value == "invisivel"
            and operation.params.get("kwargs", {}).get("target") == "self"
            and re.search(r"action\s*:\s*bonus_action\b", tag)
            for tag in tags
            for operation in evaluate_tags((tag,), context).operations
        )
        if not granted:
            raise ValueError("No bonus-action invisibility is granted")
        self.bonus_action_used = True
        self._bonus_invisible.add(actor)
        self._events.append(("invisibility_start", actor, "bonus_action"))
        return True

    def teleport_around_action(self, actor, *, action_kind, phase, distance_ft,
                               destination_ref, visible, unoccupied):
        """Record a tagged teleport immediately before or after an eligible action.

        The table resolves occupied spaces and visibility; this executor checks
        their declared facts, range, timing and one teleport per action.
        """
        self._living(actor)
        if (action_kind not in {"attack", "magic"} or phase not in {"before", "after"}
                or type(distance_ft) is not int or distance_ft < 0
                or not isinstance(destination_ref, str)
                or not 0 < len(destination_ref.strip()) <= 100
                or any(ord(char) < 32 for char in destination_ref)
                or type(visible) is not bool or type(unoccupied) is not bool
                or not visible or not unoccupied or self._teleport_used):
            raise ValueError("Invalid teleport declaration")
        if phase == "before":
            if self.finished or actor != self.current_actor or self.action_used:
                raise ValueError("Teleport must precede this actor's action")
        elif (self._action_actor_id != actor or not self.action_used
              or self._action_kind != action_kind or self._teleport_pending_kind):
            raise ValueError("Teleport must follow the declared action")
        if phase == "after":
            last = self._events[-1] if self._events else ()
            if last and last[0] == "encounter_end":
                last = self._events[-2] if len(self._events) > 1 else ()
            if (not last or last[0] not in {"attack", "action"}
                    or last[1] != actor
                    or (last[0] == "action" and last[2] != "action")):
                raise ValueError("Teleport must immediately follow the action")
        entry = self._combatants[actor]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="teleport",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        tags = entry["defensive_tags"] + tuple(
            tag for tag in entry["offensive_tags"]
            if tag not in entry["defensive_tags"])
        ranges = [operation.value for operation in evaluate_tags(tags, context).operations
                  if operation.active and operation.op == "grant_execution"
                  and operation.verb == "teleport"
                  and operation.params.get("kwargs", {}).get("dest") == "unoccupied_visible"
                  and operation.params.get("kwargs", {}).get("timing")
                  == "before_or_after_attack_or_magic_action"
                  and type(operation.value) is int and operation.value >= 0]
        if not ranges or distance_ft > max(ranges):
            raise ValueError("No tagged teleport permits this destination")
        self._teleport_used = True
        if phase == "before":
            self._teleport_pending_kind = action_kind
        self._events.append(("teleport", actor, phase, action_kind,
                             destination_ref.strip(), distance_ft))
        return distance_ft

    def register_action(self, actor, kind, *, action_kind=None):
        """Record a table-resolved action, bonus action or reaction not modeled here."""
        self._living(actor)
        if self.finished or kind not in {"action", "bonus_action", "reaction"}:
            raise ValueError("Invalid action")
        if kind == "action":
            if actor != self.current_actor or self.action_used:
                raise ValueError("No action is available")
            if action_kind not in {None, "magic"}:
                raise ValueError("Invalid action kind")
            resolved_kind = action_kind or "other"
            if (self._teleport_pending_kind is not None
                    and self._teleport_pending_kind != resolved_kind):
                raise ValueError("Complete the action declared for teleport")
            self.action_used = True
            self._action_kind = resolved_kind
            self._action_actor_id = actor
            self._teleport_pending_kind = None
        elif kind == "bonus_action":
            if action_kind is not None or self._teleport_pending_kind:
                raise ValueError("Invalid bonus action timing")
            if actor != self.current_actor or self.bonus_action_used:
                raise ValueError("No bonus action is available")
            self.bonus_action_used = True
        else:
            if action_kind is not None or self._teleport_pending_kind:
                raise ValueError("Invalid reaction timing")
            if actor in self._reactions_used:
                raise ValueError("No reaction is available")
            self._reactions_used.add(actor)
        self._break_invisibility(actor)
        self._events.append(("action", actor, kind))

    def bonus_action_dodge(self):
        """Use a bonus action to Dodge when a currently active tag grants it."""
        actor = self.current_actor
        if (self.finished or actor is None or self.bonus_action_used
                or self._teleport_pending_kind):
            raise ValueError("No bonus action is available")
        self._living(actor)
        entry = self._combatants[actor]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="dodge_action",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        tags = entry["defensive_tags"] + tuple(
            tag for tag in entry["offensive_tags"]
            if tag not in entry["defensive_tags"])
        granted = any(
            operation.active and operation.verb == "dodge"
            and operation.op == "grant_execution"
            and re.search(r"action\s*:\s*bonus_action\b", tag)
            for tag in tags
            for operation in evaluate_tags((tag,), context).operations
        )
        if not granted:
            raise ValueError("No bonus-action Dodge is granted")
        self._break_invisibility(actor)
        self.bonus_action_used = True
        self._dodge_active.add(actor)
        self._events.append(("dodge", actor, "bonus_action"))
        return True

    def dodge_defense(self, actor):
        """Tell the VTT how to resolve attack rolls and Dexterity saves."""
        if actor not in self._combatants:
            raise ValueError("Unknown combatant")
        active = actor in self._dodge_active and self._combatants[actor]["hp"] > 0
        return {"attacks_disadvantage": active, "dex_saves_advantage": active}

    def attack_reach_bonus(self, actor):
        """Reach added by the current turn's Attack action, in feet."""
        if actor not in self._combatants:
            raise ValueError("Unknown combatant")
        return self._attack_reach_bonus.get(actor, 0) if self.current_actor == actor else 0

    def escape_condition(self, condition, source, available_movement_ft):
        """Spend VTT-declared movement to end a condition when an active tag allows it.

        The caller owns movement outside this encounter. A successful result
        returns the remaining movement so the VTT can update its turn budget.
        """
        actor = self.current_actor
        if (self.finished or actor is None or
                not isinstance(condition, str) or not condition.strip() or
                not isinstance(source, str) or not source.strip() or
                type(available_movement_ft) is not int or available_movement_ft < 0):
            raise ValueError("Declare an active turn, condition, source and movement")
        condition = condition.strip().lower()
        self._living(actor)
        if "self" not in self.conditions.facts(actor, source).get(condition, ()):
            raise ValueError("Condition is not active")

        entry = self._combatants[actor]
        context = dict(entry["tag_context"])
        context.update(resolve_runtime=True, event="escape",
                       self_hp=entry["hp"], self_max_hp=entry["max_hp"])
        tags = entry["defensive_tags"] + tuple(
            tag for tag in entry["offensive_tags"]
            if tag not in entry["defensive_tags"])
        costs = []
        for operation in evaluate_tags(tags, context).operations:
            if not (operation.active and operation.verb == "escape" and
                    operation.op == "grant_execution"):
                continue
            nodes = parse_tag(operation.raw).nodes
            if len(nodes) != 1:
                continue
            arguments = {node.name: str(node.value or "").strip().lower()
                         for node in nodes[0].children}
            match = re.fullmatch(r"(\d+)ft", arguments.get("cost", ""))
            if (arguments.get("action") == "move" and
                    arguments.get("condition") == condition and match):
                costs.append(int(match.group(1)))
        if not costs:
            raise ValueError("No movement escape is granted")
        cost = min(costs)
        if available_movement_ft < cost:
            raise ValueError("Insufficient movement")
        self.conditions.remove(actor, condition, source)
        remaining = available_movement_ft - cost
        self._events.append(("escape", actor, source, condition, cost, remaining))
        return remaining

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

    def attack(self, target, tags, *, hit, damage=0, damage_type=None,
               critical=False, dodge_disadvantage_applied=False,
               melee_weapon=False, invisible_advantage_applied=False,
               invisible_disadvantage_applied=False,
               concentration_save_success=None):
        source = self._action_actor()
        if self._teleport_pending_kind not in {None, "attack"}:
            raise ValueError("Complete the magic action declared for teleport")
        self._living(target)
        tags = tuple(tags)
        if (type(hit) is not bool or type(critical) is not bool or
                (critical and not hit) or type(damage) is not int or damage < 0 or
                (damage_type is not None and
                 (not isinstance(damage_type, str) or not damage_type.strip())) or
                (not hit and damage) or type(dodge_disadvantage_applied) is not bool
                or type(melee_weapon) is not bool
                or type(invisible_advantage_applied) is not bool
                or type(invisible_disadvantage_applied) is not bool
                or (concentration_save_success is not None and
                    type(concentration_save_success) is not bool)):
            raise ValueError("Declare a valid hit and rolled damage")
        if concentration_save_success is not None and (
                not hit or damage == 0 or target not in self._concentration):
            raise ValueError("No concentration damage save is available")
        if target in self._dodge_active and not dodge_disadvantage_applied:
            raise ValueError("Resolve the dodging target's attack disadvantage")
        if self.invisibility_state(source) and not invisible_advantage_applied:
            raise ValueError("Resolve the invisible attacker's advantage")
        if self.invisibility_state(target) and not invisible_disadvantage_applied:
            raise ValueError("Resolve the invisible target's attack disadvantage")
        if melee_weapon:
            source_entry = self._combatants[source]
            attack_context = dict(source_entry["tag_context"])
            attack_context.update(resolve_runtime=True, event="attack_action",
                                  self_hp=source_entry["hp"],
                                  self_max_hp=source_entry["max_hp"])
            reach_tags = source_entry["offensive_tags"] + tuple(
                tag for tag in tags if tag not in source_entry["offensive_tags"])
            reach_bonus = sum(
                operation.value for tag in reach_tags
                for operation in evaluate_tags((tag,), attack_context).operations
                if operation.active and operation.verb == "reach"
                and operation.op == "add_modifier"
                and type(operation.value) is int and operation.value > 0
            )
            if reach_bonus:
                self._attack_reach_bonus[source] = reach_bonus
        operations = None
        if hit:
            source_entry = self._combatants[source]
            attack_context = dict(source_entry["tag_context"])
            attack_context.update(resolve_runtime=True, event="hit",
                                  self_hp=source_entry["hp"],
                                  self_max_hp=source_entry["max_hp"])
            # A ficha pode entregar a mesma tag passiva na fonte do atacante e
            # nas tags declaradas para o golpe. Conte-a uma vez nesse caso;
            # fontes distintas no conjunto do atacante continuam cumulativas.
            source_tags = source_entry["offensive_tags"]
            attack_effects = evaluate_tags(
                source_tags + tuple(tag for tag in tags if tag not in source_tags),
                attack_context)
            ignored = ignored_resistance_types(attack_effects.operations)
            if critical and damage_type is not None:
                damage += critical_damage_bonus(attack_effects.operations)
            operations = self.conditions.resolve(
                tags, event="hit", source=source, target=target)
            damage = self._damage_after_defenses(
                target, damage, damage_type.strip().lower()
                if isinstance(damage_type, str) else None, ignored)
            if concentration_save_success is not None and damage == 0:
                raise ValueError("No concentration damage save is available")
            target_entry = self._combatants[target]
            absorbed = min(target_entry["temp_hp"], damage)
            target_entry["temp_hp"] -= absorbed
            target_entry["hp"] = max(0, target_entry["hp"] - (damage - absorbed))
            if damage > 0 and target in self._concentration:
                if target_entry["hp"] == 0:
                    self.resolve_concentration_event(target, "unconscious")
                else:
                    self.resolve_concentration_event(
                        target, "damage", save_success=concentration_save_success)
        self.action_used = True
        self._action_kind = "attack"
        self._action_actor_id = source
        self._teleport_pending_kind = None
        self._break_invisibility(source)
        self._events.append(("attack", source, target, hit, damage))
        self._finish_if_decided()
        return operations

    def heal(self, target, amount):
        source = self._action_actor()
        if self._teleport_pending_kind:
            raise ValueError("Complete the declared action for teleport")
        self._living(target)
        if type(amount) is not int or amount < 0:
            raise ValueError("Declare a nonnegative healing amount")
        self._break_invisibility(source)
        blocked = self.conditions.blocks_healing(target)
        if not blocked:
            entry = self._combatants[target]
            bonus = (self._healing_tag_bonus(target)
                     if amount and entry["hp"] < entry["max_hp"] else 0)
            entry["hp"] = min(entry["max_hp"], entry["hp"] + amount + bonus)
        self.action_used = True
        self._action_kind = "heal"
        self._action_actor_id = source
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
        if self._teleport_pending_kind:
            raise ValueError("Complete the declared action for teleport")
        self._living(target)
        if type(amount) is not int or amount < 0:
            raise ValueError("Declare a nonnegative temporary HP amount")
        self._break_invisibility(source)
        entry = self._combatants[target]
        received = (amount + self._temporary_hp_tag_bonus(target)
                    if amount else 0)
        entry["temp_hp"] = max(entry["temp_hp"], received)
        self.action_used = True
        self._action_kind = "temporary_hp"
        self._action_actor_id = source
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
        if self._teleport_pending_kind:
            raise ValueError("Complete the action declared for teleport")
        self._events.append(("turn_end", self.current_actor))
        self._attack_reach_bonus.pop(self.current_actor, None)
        self.current_actor = None
        self.action_used = False
        self.bonus_action_used = False

    def _finish_if_decided(self):
        living_teams = {
            entry["team"] for entry in self._combatants.values() if entry["hp"] > 0
        }
        if len(living_teams) == 1:
            self.finished = True
            self._events.append(("encounter_end", next(iter(living_teams))))
            self.current_actor = None
