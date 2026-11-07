"""Generic runtime contracts needed by sky themed epic effects.

The helpers in this module consume tag operations by operation/target and never
inspect a talent, feature, or spell name.
"""


def consume_movement_operation(operation, movement_properties, fall_rule):
    """Merge optional movement qualifiers emitted by ``move`` operations.

    Returns true when at least one qualifier was consumed. Reapplying the same
    operation is idempotent; when several sources exist, the most protective
    falling limits win.
    """
    if ((operation.op, operation.target)
            != ("add_to_set", "movimento.modos")):
        return False

    params = operation.params or {}
    mode = params.get("name")
    if not mode:
        return False
    flags = set(params.get("flags") or ())
    kwargs = params.get("kwargs") or {}
    consumed = False

    if "hover" in flags or kwargs.get("hover") is True:
        movement_properties.setdefault(mode, {})["hover"] = True
        consumed = True

    threshold = kwargs.get("fall_threshold")
    speed = kwargs.get("fall_speed")
    if (isinstance(threshold, (int, float)) and threshold >= 0
            and isinstance(speed, (int, float)) and speed > 0):
        threshold = int(threshold)
        speed = int(speed)
        current_threshold = fall_rule.get("threshold_ft")
        current_speed = fall_rule.get("max_per_turn_ft")
        fall_rule["threshold_ft"] = (threshold if current_threshold is None
                                     else min(current_threshold, threshold))
        fall_rule["max_per_turn_ft"] = (speed if current_speed is None
                                        else min(current_speed, speed))
        consumed = True
    return consumed


def fall_distance_for_turn(sheet, remaining_distance_ft):
    """Resolve one turn of falling from the derived sheet's generic rule."""
    remaining = max(0, int(remaining_distance_ft or 0))
    rule = (sheet or {}).get("queda_controlada") or {}
    threshold = rule.get("threshold_ft")
    maximum = rule.get("max_per_turn_ft")
    if (not isinstance(threshold, (int, float))
            or not isinstance(maximum, (int, float))
            or remaining <= threshold):
        return remaining
    return min(remaining, int(maximum))
