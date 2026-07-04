from __future__ import annotations

import copy
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


@dataclass
class RuleDef:
    id: str
    title: str
    trigger_kind: str
    trigger_clock_id: str | None
    trigger_event: str | None
    condition: dict
    effects: list[dict]
    enabled: bool


@dataclass
class Effect:
    clock_id: str
    delta: int
    reason: str
    rule_id: str | None
    hop_depth: int
    caused_by: str = "manual"  # overridden only by non-rule system sources (e.g. drift_adopt)


@dataclass
class AppliedTick:
    clock_id: str
    delta: int
    filled_before: int
    filled_after: int
    reason: str
    caused_by: str
    rule_id: str | None
    hop_depth: int
    events: list[str] = field(default_factory=list)


@dataclass
class SkippedEffect:
    clock_id: str
    delta: int
    rule_id: str | None
    hop_depth: int
    why: str


@dataclass
class FireResult:
    applied: list[AppliedTick] = field(default_factory=list)
    skipped: list[SkippedEffect] = field(default_factory=list)
    guard_trips: list[str] = field(default_factory=list)
    final_state: dict[str, ClockState] = field(default_factory=dict)


def render_reason(template: str, rule_title: str, trigger_note: str) -> str:
    if not template.strip():
        return rule_title or "cascade effect"
    out = template.replace("{rule_title}", rule_title).replace("{trigger_note}", trigger_note)
    return out.strip() or rule_title or "cascade effect"


def _apply_effect(effect: Effect, clocks: dict[str, ClockState], result: FireResult) -> AppliedTick | None:
    clock = clocks.get(effect.clock_id)
    if clock is None:
        result.skipped.append(SkippedEffect(
            effect.clock_id, effect.delta, effect.rule_id, effect.hop_depth,
            "clock not found",
        ))
        return None
    if clock.lifecycle != "active":
        result.skipped.append(SkippedEffect(
            effect.clock_id, effect.delta, effect.rule_id, effect.hop_depth,
            f"clock is not active (lifecycle={clock.lifecycle})",
        ))
        return None
    before = clock.filled
    after = max(0, min(clock.segments, before + effect.delta))
    if after == before:
        boundary = "full" if before >= clock.segments else "empty" if before <= 0 else "unchanged"
        result.skipped.append(SkippedEffect(
            effect.clock_id, effect.delta, effect.rule_id, effect.hop_depth,
            f"no-op: clock already {boundary}",
        ))
        return None
    clock.filled = after
    events = ["ticked"]
    if after == clock.segments and before < clock.segments:
        events.append("filled")
    if after == 0 and before > 0:
        events.append("emptied")
    tick = AppliedTick(
        clock_id=effect.clock_id,
        delta=after - before,
        filled_before=before,
        filled_after=after,
        reason=effect.reason,
        caused_by="rule" if effect.rule_id else effect.caused_by,
        rule_id=effect.rule_id,
        hop_depth=effect.hop_depth,
        events=events,
    )
    result.applied.append(tick)
    return tick


def project_fire(
    initial_effects: list[Effect],
    clocks: dict[str, ClockState],
    rules: list[RuleDef],
) -> FireResult:
    state = copy.deepcopy(clocks)
    result = FireResult()
    fired: set[str] = set()
    queue = list(initial_effects)

    while queue:
        effect = queue.pop(0)
        tick = _apply_effect(effect, state, result)
        if tick is None:
            continue
        for event in tick.events:
            for candidate in rules:
                if not candidate.enabled or candidate.trigger_kind != "clock_event":
                    continue
                if candidate.trigger_clock_id != tick.clock_id:
                    continue
                if candidate.trigger_event != event:
                    continue
                if candidate.id in fired:
                    result.guard_trips.append(
                        f"rule {candidate.id} suppressed: fires once per trigger"
                    )
                    continue
                if tick.hop_depth + 1 > MAX_DEPTH:
                    result.guard_trips.append(
                        f"rule {candidate.id} suppressed: max chain depth {MAX_DEPTH}"
                    )
                    continue
                if not evaluate_condition(candidate.condition, state):
                    continue
                fired.add(candidate.id)
                for rule_effect in candidate.effects:
                    queue.append(Effect(
                        clock_id=str(rule_effect["clock_id"]),
                        delta=int(rule_effect["delta"]),
                        reason=render_reason(
                            rule_effect.get("reason_template", ""), candidate.title, "",
                        ),
                        rule_id=candidate.id,
                        hop_depth=tick.hop_depth + 1,
                    ))
    result.final_state = state
    return result
