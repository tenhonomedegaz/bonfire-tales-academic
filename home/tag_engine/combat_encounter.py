"""In-memory encounter execution with declared hit and damage outcomes.

The table/VTT supplies dice outcomes and turn order. This executor owns HP,
action use, condition timing and healing restrictions for one encounter; it
does not persist characters or pretend to resolve every RPG combat rule.
"""

from .combat_conditions import CombatConditions


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
            if (not isinstance(actor, str) or not actor or actor in self._combatants or
                    not isinstance(team, str) or not team or
                    type(maximum) is not int or maximum <= 0 or
                    type(hp) is not int or not 0 < hp <= maximum):
                raise ValueError("Invalid combatant")
            self._combatants[actor] = {"team": team, "max_hp": maximum, "hp": hp}
        if len({entry["team"] for entry in self._combatants.values()}) < 2:
            raise ValueError("An encounter needs at least two teams")
        self.conditions = CombatConditions()
        self.current_actor = None
        self.action_used = False
        self.finished = False
        self._events = []

    @property
    def combatants(self):
        return {actor: entry.copy() for actor, entry in self._combatants.items()}

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
        self.current_actor = actor
        self.action_used = False
        self._events.append(("turn_start", actor, turn_id))
        return True

    def attack(self, target, tags, *, hit, damage=0):
        source = self._action_actor()
        self._living(target)
        if (type(hit) is not bool or type(damage) is not int or damage < 0 or
                (not hit and damage)):
            raise ValueError("Declare a valid hit and rolled damage")
        operations = None
        if hit:
            operations = self.conditions.resolve(
                tags, event="hit", source=source, target=target)
            self._combatants[target]["hp"] = max(
                0, self._combatants[target]["hp"] - damage)
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
            entry["hp"] = min(entry["max_hp"], entry["hp"] + amount)
        self.action_used = True
        self._events.append(("heal", source, target, amount, blocked))
        return not blocked

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
