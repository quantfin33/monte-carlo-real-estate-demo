from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.ui_app_helpers import (
    all_visible_text,
    assert_no_unsafe_visible_phrases,
    element_by_label,
    rerun_app,
    run_app_once,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ui_numeric_cases.json"


def _cases() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


def _activate_case(app, case: dict[str, object]):
    activation_checkbox = case.get("activation_checkbox")
    if activation_checkbox:
        element_by_label(app.checkbox, str(activation_checkbox)).set_value(True)
        app = rerun_app(app)
    return app


def _assert_within_declared_bounds(widget) -> None:
    minimum = getattr(widget, "min", None)
    maximum = getattr(widget, "max", None)
    value = widget.value
    if minimum is not None:
        assert value >= minimum, f"{widget.label} default {value} below minimum {minimum}"
    if maximum is not None:
        assert value <= maximum, f"{widget.label} default {value} above maximum {maximum}"


def test_numeric_boundary_fixture_is_small_and_well_formed():
    cases = _cases()
    assert 10 <= len(cases) <= 25
    seen_labels = set()
    for case in cases:
        assert case["label"] not in seen_labels
        seen_labels.add(case["label"])
        assert case["category"] in {"engine_input", "ui_workflow"}
        assert len(case["values"]) == 2


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["label"])
def test_numeric_control_defaults_are_inside_streamlit_bounds(case):
    app = _activate_case(run_app_once(), case)
    widget = element_by_label(app.number_input, str(case["label"]))
    _assert_within_declared_bounds(widget)
    assert_no_unsafe_visible_phrases(all_visible_text(app))


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["label"])
def test_numeric_control_low_high_values_are_accepted_without_simulation(case):
    for value in case["values"]:
        app = _activate_case(run_app_once(), case)
        widget = element_by_label(app.number_input, str(case["label"]))
        widget.set_value(value)
        app = rerun_app(app)
        updated = element_by_label(app.number_input, str(case["label"]))
        assert updated.value == pytest.approx(value)
        _assert_within_declared_bounds(updated)
        assert_no_unsafe_visible_phrases(all_visible_text(app))
