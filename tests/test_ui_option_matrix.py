from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.ui_app_helpers import (
    all_visible_text,
    assert_no_unsafe_visible_phrases,
    element_by_label,
    labels,
    rerun_app,
    run_app_once,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ui_option_matrix.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


OPTION_MATRIX = _fixture()


def _activate(app, spec: dict[str, object]):
    activation_checkbox = spec.get("activation_checkbox")
    if activation_checkbox:
        element_by_label(app.checkbox, str(activation_checkbox)).set_value(True)
        app = rerun_app(app)

    activation_selectbox = spec.get("activation_selectbox")
    if activation_selectbox:
        activation = dict(activation_selectbox)
        element_by_label(app.selectbox, str(activation["label"])).set_value(str(activation["value"]))
        app = rerun_app(app)

    return app


def _options(widget) -> list[str]:
    return [str(option) for option in getattr(widget, "options", [])]


def test_option_matrix_fixture_matches_current_visible_and_conditional_options():
    for spec in OPTION_MATRIX["selectboxes"]:
        app = _activate(run_app_once(), spec)
        widget = element_by_label(app.selectbox, str(spec["label"]))
        assert _options(widget) == spec["options"]
        assert spec["category"] in {"engine_input", "ui_workflow"}
        assert_no_unsafe_visible_phrases(all_visible_text(app))

    app = run_app_once()
    assert labels(app.checkbox) == OPTION_MATRIX["checkboxes"]

    for spec in OPTION_MATRIX["multiselects"]:
        app = _activate(run_app_once(), spec)
        widget = element_by_label(app.multiselect, str(spec["label"]))
        assert _options(widget) == spec["options"]
        assert_no_unsafe_visible_phrases(all_visible_text(app))


@pytest.mark.parametrize("spec", OPTION_MATRIX["selectboxes"], ids=lambda spec: spec["label"])
def test_every_selectbox_option_can_be_selected_without_exception(spec):
    for option in spec["options"]:
        app = _activate(run_app_once(), spec)
        element_by_label(app.selectbox, str(spec["label"])).set_value(option)
        app = rerun_app(app)
        assert element_by_label(app.selectbox, str(spec["label"])).value == option
        assert_no_unsafe_visible_phrases(all_visible_text(app))


@pytest.mark.parametrize("label", OPTION_MATRIX["checkboxes"])
def test_every_checkbox_can_be_toggled_true_and_false_without_exception(label):
    for value in (True, False):
        app = run_app_once()
        element_by_label(app.checkbox, label).set_value(value)
        app = rerun_app(app)
        assert element_by_label(app.checkbox, label).value is value
        assert_no_unsafe_visible_phrases(all_visible_text(app))


@pytest.mark.parametrize("spec", OPTION_MATRIX["multiselects"], ids=lambda spec: spec["label"])
def test_multiselect_option_cases_can_be_selected_without_exception(spec):
    for selected in spec["cases"]:
        app = _activate(run_app_once(), spec)
        widget = element_by_label(app.multiselect, str(spec["label"]))
        widget.set_value(selected)
        app = rerun_app(app)
        assert element_by_label(app.multiselect, str(spec["label"])).value == selected
        assert_no_unsafe_visible_phrases(all_visible_text(app))
