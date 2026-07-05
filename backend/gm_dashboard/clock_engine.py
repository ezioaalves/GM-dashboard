from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field

import psycopg2.extras


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


class EngineError(ValueError):
    """Domain error: bad tick/fire request. Routers map to HTTP 409/422."""


def _load_state(cur) -> dict[str, ClockState]:
    cur.execute("SELECT id, kind, segments, filled, lifecycle FROM clocks FOR UPDATE")
    return {
        str(row["id"]): ClockState(
            id=str(row["id"]), kind=row["kind"], segments=row["segments"],
            filled=row["filled"], lifecycle=row["lifecycle"],
        )
        for row in cur.fetchall()
    }


def _load_rules(cur) -> list[RuleDef]:
    cur.execute(
        """
        SELECT id, title, trigger_kind, trigger_clock_id, trigger_event,
               condition, effects, enabled
        FROM cascade_rules WHERE enabled = true
        """
    )
    return [
        RuleDef(
            id=str(row["id"]), title=row["title"] or "",
            trigger_kind=row["trigger_kind"],
            trigger_clock_id=str(row["trigger_clock_id"]) if row["trigger_clock_id"] else None,
            trigger_event=row["trigger_event"],
            condition=row["condition"] or {}, effects=row["effects"] or [],
            enabled=row["enabled"],
        )
        for row in cur.fetchall()
    ]


def _write_fire_result(cur, fire_id: str, result: FireResult) -> None:
    for tick in result.applied:
        cur.execute(
            """
            INSERT INTO clock_ticks
              (clock_id, delta, filled_before, filled_after, reason,
               caused_by, rule_id, trigger_fire_id, hop_depth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tick.clock_id, tick.delta, tick.filled_before, tick.filled_after,
                tick.reason, tick.caused_by, tick.rule_id, fire_id, tick.hop_depth,
            ),
        )
        cur.execute(
            "UPDATE clocks SET filled = %s, updated_at = now() WHERE id = %s",
            (tick.filled_after, tick.clock_id),
        )


def _insert_push_job(cur, clock: dict, env: str) -> str:
    cur.execute(
        """
        INSERT INTO sync_jobs (
          target, direction, status, diff, job_type,
          source_surface, target_surface, payload, input_payload,
          started_at, updated_at
        )
        VALUES (
          %(target)s, 'postgres_to_foundry', 'running', '', 'clock_push',
          'postgres', %(target_surface)s, %(payload)s, %(payload)s, now(), now()
        )
        RETURNING id
        """,
        {
            "target": f"clock:{clock['id']}:{env}",
            "target_surface": f"foundry_{env}",
            "payload": psycopg2.extras.Json({"clock_id": str(clock["id"]), "env": env}),
        },
    )
    return str(cur.fetchone()["id"])


def _complete_push_job(cur, job_id: str, entry: dict) -> None:
    cur.execute(
        """
        UPDATE sync_jobs
        SET status = 'succeeded',
            result = %(result)s,
            result_payload = %(result)s,
            finished_at = now(),
            updated_at = now()
        WHERE id = %(id)s
        """,
        {"id": job_id, "result": psycopg2.extras.Json({"entry": entry})},
    )


def _fail_push_job(cur, job_id: str, error: str) -> None:
    cur.execute(
        """
        UPDATE sync_jobs
        SET status = 'failed',
            error = %(error)s,
            error_code = 'clock_push_failed',
            error_message = %(error)s,
            finished_at = now(),
            updated_at = now()
        WHERE id = %(id)s
        """,
        {"id": job_id, "error": error},
    )


def push_mirrors_for_clocks(conn, clock_ids: set[str]) -> None:
    if not clock_ids:
        return
    from . import clockworks_mirror

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM clocks
            WHERE id::text = ANY(%s)
              AND (foundry_clock_id_test <> '' OR foundry_clock_id_prod <> '')
              AND mirror_state <> 'not_mirrored'
            """,
            (list(clock_ids),),
        )
        rows = [dict(row) for row in cur.fetchall()]
        for clock in rows:
            for env in ("test", "prod"):
                foundry_id = clock[f"foundry_clock_id_{env}"]
                if not foundry_id:
                    continue
                job_id = _insert_push_job(cur, clock, env)
                try:
                    client = clockworks_mirror.load_relay_client(env)
                    entry = clockworks_mirror.render_clockworks_entry(clock, foundry_id)
                    clockworks_mirror.push_entry(client, entry)
                    cur.execute(
                        """
                        UPDATE clocks
                        SET last_mirrored_at = now(),
                            mirror_state = 'mirrored',
                            freshness_state = 'fresh',
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (clock["id"],),
                    )
                    _complete_push_job(cur, job_id, entry)
                except Exception as exc:
                    cur.execute(
                        "UPDATE clocks SET mirror_state = 'failed', updated_at = now() WHERE id = %s",
                        (clock["id"],),
                    )
                    _fail_push_job(cur, job_id, str(exc))


def _push_mirrors_after_fire(conn, fire_result: dict) -> None:
    push_mirrors_for_clocks(conn, {tick["clock_id"] for tick in fire_result["applied"]})


def _result_payload(fire_id: str, result: FireResult, dry_run: bool) -> dict:
    return {
        "trigger_fire_id": fire_id,
        "dry_run": dry_run,
        "applied": [
            {
                "clock_id": t.clock_id, "delta": t.delta,
                "filled_before": t.filled_before, "filled_after": t.filled_after,
                "reason": t.reason, "caused_by": t.caused_by, "rule_id": t.rule_id,
                "hop_depth": t.hop_depth, "events": t.events,
                "trigger_fire_id": fire_id,
            }
            for t in result.applied
        ],
        "skipped": [
            {"clock_id": s.clock_id, "delta": s.delta, "rule_id": s.rule_id,
             "hop_depth": s.hop_depth, "why": s.why}
            for s in result.skipped
        ],
        "guard_trips": result.guard_trips,
        "clocks": {
            cid: {"filled": c.filled, "segments": c.segments}
            for cid, c in result.final_state.items()
        },
    }


def _run_fire(conn, initial_effects: list[Effect], dry_run: bool,
              condition: dict | None = None) -> dict:
    fire_id = str(uuid.uuid4())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            clocks = _load_state(cur)
            if condition is not None and not evaluate_condition(condition, clocks):
                raise EngineError("rule condition is not met")
            rules = _load_rules(cur)
            result = project_fire(initial_effects, clocks, rules)
            if dry_run:
                conn.rollback()  # release FOR UPDATE locks
                return _result_payload(fire_id, result, True)
            _write_fire_result(cur, fire_id, result)
        payload = _result_payload(fire_id, result, False)
        _push_mirrors_after_fire(conn, payload)
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise


def fire_manual_tick(conn, clock_id: str, delta: int, reason: str, dry_run: bool = False,
                     caused_by: str = "manual") -> dict:
    if not reason or not reason.strip():
        raise EngineError("reason is required")
    if delta == 0:
        raise EngineError("delta must be non-zero")
    # Pre-check for a friendly EngineError; safe against races because
    # _apply_effect re-validates existence + lifecycle against the
    # FOR UPDATE-locked state inside _run_fire (worst case: skipped, never
    # a wrong write).
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT lifecycle FROM clocks WHERE id = %s", (clock_id,))
        row = cur.fetchone()
    if row is None:
        raise EngineError("clock not found")
    if row["lifecycle"] != "active":
        raise EngineError(f"clock is not active (lifecycle={row['lifecycle']})")
    effect = Effect(clock_id=clock_id, delta=delta, reason=reason.strip(),
                    rule_id=None, hop_depth=0, caused_by=caused_by)
    return _run_fire(conn, [effect], dry_run)


def fire_rule(conn, rule_id: str, trigger_note: str = "", dry_run: bool = False) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM cascade_rules WHERE id = %s", (rule_id,))
        row = cur.fetchone()
    if row is None:
        raise EngineError("cascade rule not found")
    if not row["enabled"]:
        raise EngineError("cascade rule is disabled")
    if row["trigger_kind"] != "manual":
        raise EngineError("only manual rules can be fired directly")
    initial = [
        Effect(
            clock_id=str(e["clock_id"]), delta=int(e["delta"]),
            reason=render_reason(e.get("reason_template", ""), row["title"] or row["name"],
                                 trigger_note),
            rule_id=str(row["id"]), hop_depth=0,
        )
        for e in (row["effects"] or [])
    ]
    if not initial:
        raise EngineError("rule has no effects")
    # Condition is evaluated inside _run_fire against the same FOR UPDATE-locked
    # state the fire uses — one transaction, no peek-and-release TOCTOU window.
    return _run_fire(conn, initial, dry_run, condition=row["condition"] or {})
