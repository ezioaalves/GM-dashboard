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
