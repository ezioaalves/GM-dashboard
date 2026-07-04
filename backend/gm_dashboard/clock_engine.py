from __future__ import annotations

import math
from dataclasses import dataclass, field


MAX_DEPTH = 5

_OPS = {
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "eq": lambda a, b: a == b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}

_SYMBOLIC_VALUES = {"half", "full"}


class ConditionError(ValueError):
    """Raised when a cascade condition is malformed or references unknown clocks."""


@dataclass
class ClockState:
    id: str
    kind: str
    segments: int
    filled: int
    lifecycle: str


def validate_condition(condition: object) -> None:
    if not isinstance(condition, dict):
        raise ConditionError("condition must be an object")
    if condition == {}:
        return
    keys = set(condition)
    if keys == {"all"} or keys == {"any"}:
        branches = condition.get("all", condition.get("any"))
        if not isinstance(branches, list) or not branches:
            raise ConditionError("all/any must hold a non-empty list")
        for branch in branches:
            validate_condition(branch)
        return
    if "clock" in keys:
        if not isinstance(condition["clock"], str) or not condition["clock"]:
            raise ConditionError("clock leaf needs a clock id")
        if keys == {"clock", "lifecycle"}:
            if condition["lifecycle"] not in {"active", "resolved", "abandoned"}:
                raise ConditionError(f"unknown lifecycle {condition['lifecycle']!r}")
            return
        if keys == {"clock", "op", "value"}:
            if condition["op"] not in _OPS:
                raise ConditionError(f"unknown op {condition['op']!r}")
            value = condition["value"]
            if not (isinstance(value, int) and not isinstance(value, bool)) and (
                value not in _SYMBOLIC_VALUES
            ):
                raise ConditionError(f"value must be an int, 'half' or 'full', got {value!r}")
            return
        raise ConditionError(f"malformed clock leaf keys: {sorted(keys)}")
    raise ConditionError(f"unknown condition keys: {sorted(keys)}")


def _resolve_value(value: object, clock: ClockState) -> int:
    if value == "half":
        return math.ceil(clock.segments / 2)
    if value == "full":
        return clock.segments
    return int(value)  # validated as int already


def evaluate_condition(condition: dict, clocks: dict[str, ClockState]) -> bool:
    validate_condition(condition)
    return _evaluate(condition, clocks)


def _evaluate(condition: dict, clocks: dict[str, ClockState]) -> bool:
    if condition == {}:
        return True
    if "all" in condition:
        return all(_evaluate(branch, clocks) for branch in condition["all"])
    if "any" in condition:
        return any(_evaluate(branch, clocks) for branch in condition["any"])
    clock = clocks.get(condition["clock"])
    if clock is None:
        raise ConditionError(f"condition references unknown clock {condition['clock']!r}")
    if "lifecycle" in condition:
        return clock.lifecycle == condition["lifecycle"]
    return _OPS[condition["op"]](clock.filled, _resolve_value(condition["value"], clock))
