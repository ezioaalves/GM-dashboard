from __future__ import annotations

import pytest

from gm_dashboard.clock_engine import (
    ClockState,
    ConditionError,
    evaluate_condition,
    validate_condition,
)


def clock(cid="c1", kind="progress", segments=6, filled=3, lifecycle="active"):
    return ClockState(id=cid, kind=kind, segments=segments, filled=filled, lifecycle=lifecycle)


CLOCKS = {"c1": clock(), "c2": clock("c2", segments=8, filled=8)}


class TestConditionDSL:
    def test_empty_condition_is_true(self):
        assert evaluate_condition({}, CLOCKS) is True

    @pytest.mark.parametrize(
        "op,value,expected",
        [
            ("gte", 3, True), ("gte", 4, False),
            ("gt", 2, True), ("gt", 3, False),
            ("eq", 3, True), ("eq", 4, False),
            ("lt", 4, True), ("lt", 3, False),
            ("lte", 3, True), ("lte", 2, False),
        ],
    )
    def test_comparison_ops(self, op, value, expected):
        cond = {"clock": "c1", "op": op, "value": value}
        assert evaluate_condition(cond, CLOCKS) is expected

    def test_half_and_full_values(self):
        # c1: segments=6, half = ceil(6/2) = 3, filled = 3
        assert evaluate_condition({"clock": "c1", "op": "gte", "value": "half"}, CLOCKS)
        assert not evaluate_condition({"clock": "c1", "op": "gte", "value": "full"}, CLOCKS)
        assert evaluate_condition({"clock": "c2", "op": "eq", "value": "full"}, CLOCKS)

    def test_half_rounds_up(self):
        clocks = {"c7": clock("c7", segments=7, filled=4)}
        assert evaluate_condition({"clock": "c7", "op": "gte", "value": "half"}, clocks)
        clocks["c7"].filled = 3
        assert not evaluate_condition({"clock": "c7", "op": "gte", "value": "half"}, clocks)

    def test_lifecycle_leaf(self):
        assert evaluate_condition({"clock": "c1", "lifecycle": "active"}, CLOCKS)
        assert not evaluate_condition({"clock": "c1", "lifecycle": "resolved"}, CLOCKS)

    def test_all_any_nesting(self):
        cond = {"all": [
            {"clock": "c1", "op": "gte", "value": 1},
            {"any": [
                {"clock": "c2", "op": "eq", "value": "full"},
                {"clock": "c1", "lifecycle": "resolved"},
            ]},
        ]}
        assert evaluate_condition(cond, CLOCKS) is True

    def test_unknown_clock_raises(self):
        with pytest.raises(ConditionError):
            evaluate_condition({"clock": "nope", "op": "gte", "value": 1}, CLOCKS)

    def test_malformed_raises(self):
        for bad in (
            {"clock": "c1"},                                # no op/lifecycle
            {"clock": "c1", "op": "between", "value": 1},   # unknown op
            {"clock": "c1", "op": "gte", "value": "third"}, # bad symbolic value
            {"all": "not-a-list"},
            {"nonsense": True},
        ):
            with pytest.raises(ConditionError):
                validate_condition(bad)

    def test_validate_accepts_good_conditions(self):
        validate_condition({})
        validate_condition({"clock": "x", "op": "lte", "value": "half"})
        validate_condition({"any": [{"clock": "x", "lifecycle": "active"}]})


from gm_dashboard.clock_engine import (
    AppliedTick,
    Effect,
    FireResult,
    RuleDef,
    project_fire,
    render_reason,
)


def rule(rid, effects, trigger_kind="clock_event", trigger_clock_id="c1",
         trigger_event="ticked", condition=None, enabled=True, title=""):
    return RuleDef(
        id=rid, title=title or rid, trigger_kind=trigger_kind,
        trigger_clock_id=trigger_clock_id, trigger_event=trigger_event,
        condition=condition or {}, effects=effects, enabled=enabled,
    )


def manual_effect(clock_id="c1", delta=1, reason="manual tick"):
    return Effect(clock_id=clock_id, delta=delta, reason=reason, rule_id=None, hop_depth=0)


class TestProjectFire:
    def test_single_manual_tick(self):
        clocks = {"c1": clock()}
        result = project_fire([manual_effect()], clocks, [])
        assert len(result.applied) == 1
        tick = result.applied[0]
        assert (tick.filled_before, tick.filled_after) == (3, 4)
        assert tick.events == ["ticked"]
        assert result.final_state["c1"].filled == 4
        assert clocks["c1"].filled == 3  # input untouched

    def test_fill_boundary_emits_filled(self):
        clocks = {"c1": clock(filled=5)}
        result = project_fire([manual_effect()], clocks, [])
        assert result.applied[0].events == ["ticked", "filled"]

    def test_empty_boundary_emits_emptied(self):
        clocks = {"c1": clock(kind="countdown", filled=1)}
        result = project_fire([manual_effect(delta=-1)], clocks, [])
        assert result.applied[0].events == ["ticked", "emptied"]

    def test_clamp_to_noop_is_skipped(self):
        clocks = {"c1": clock(filled=6)}
        result = project_fire([manual_effect(delta=2)], clocks, [])
        assert result.applied == []
        assert len(result.skipped) == 1
        assert "full" in result.skipped[0].why

    def test_partial_clamp_applies_clamped_delta(self):
        clocks = {"c1": clock(filled=5)}
        result = project_fire([manual_effect(delta=3)], clocks, [])
        assert result.applied[0].delta == 1
        assert result.applied[0].filled_after == 6

    def test_chained_rule_fires(self):
        clocks = {"c1": clock(), "c2": clock("c2", filled=0)}
        chain = rule("r1", [{"clock_id": "c2", "delta": 1, "reason_template": "{rule_title}"}])
        result = project_fire([manual_effect()], clocks, [chain])
        assert [t.clock_id for t in result.applied] == ["c1", "c2"]
        assert result.applied[1].hop_depth == 1
        assert result.applied[1].caused_by == "rule"
        assert result.applied[1].rule_id == "r1"

    def test_condition_gates_effects(self):
        clocks = {"c1": clock(), "c2": clock("c2", filled=0)}
        gated = rule(
            "r1",
            [{"clock_id": "c2", "delta": 1, "reason_template": "x"}],
            condition={"clock": "c1", "op": "gte", "value": "full"},
        )
        result = project_fire([manual_effect()], clocks, [gated])
        assert [t.clock_id for t in result.applied] == ["c1"]

    def test_rule_fires_once_per_fire(self):
        # r1 ticks c1 on c1.ticked — would loop forever without the once-guard
        clocks = {"c1": clock(filled=0)}
        loop = rule("r1", [{"clock_id": "c1", "delta": 1, "reason_template": "x"}])
        result = project_fire([manual_effect()], clocks, [loop])
        assert len(result.applied) == 2  # manual + one rule firing
        assert any("once" in trip for trip in result.guard_trips)

    def test_max_depth_guard(self):
        # chain c1 -> c2 -> c3 -> c4 -> c5 -> c6 -> c7 exceeds MAX_DEPTH=5
        clocks = {f"c{i}": clock(f"c{i}", filled=0, segments=8) for i in range(1, 8)}
        rules = [
            rule(
                f"r{i}",
                [{"clock_id": f"c{i + 1}", "delta": 1, "reason_template": "x"}],
                trigger_clock_id=f"c{i}",
            )
            for i in range(1, 7)
        ]
        result = project_fire([manual_effect(clock_id="c1")], clocks, rules)
        depths = [t.hop_depth for t in result.applied]
        assert max(depths) == 5
        assert any("depth" in trip for trip in result.guard_trips)

    def test_disabled_and_nonactive_are_ignored(self):
        clocks = {"c1": clock(), "c2": clock("c2", lifecycle="resolved", filled=0)}
        rules = [
            rule("off", [{"clock_id": "c2", "delta": 1, "reason_template": "x"}], enabled=False),
            rule("onto-resolved", [{"clock_id": "c2", "delta": 1, "reason_template": "x"}]),
        ]
        result = project_fire([manual_effect()], clocks, rules)
        # disabled rule never fires; enabled rule fires but its effect on a
        # resolved clock is skipped, not applied
        assert [t.clock_id for t in result.applied] == ["c1"]
        assert any(s.clock_id == "c2" and "active" in s.why for s in result.skipped)


class TestRenderReason:
    def test_substitutes_placeholders(self):
        out = render_reason("Failed patrol — {rule_title} ({trigger_note})", "Patrol", "s12")
        assert out == "Failed patrol — Patrol (s12)"

    def test_never_raises_on_bad_template(self):
        assert render_reason("{unknown} {", "t", "n")  # returns non-empty string

    def test_empty_template_falls_back_to_rule_title(self):
        assert render_reason("", "Patrol", "") == "Patrol"
