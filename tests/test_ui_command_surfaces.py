from __future__ import annotations

from tests.ui_app_helpers import (
    all_visible_text,
    assert_no_unsafe_visible_phrases,
    element_by_label,
    labels,
    rerun_app,
    run_app_once,
    values,
)


def _button_by_label_contains(app, needle: str):
    matches = [button for button in app.button if needle in str(getattr(button, "label", ""))]
    assert matches, f"Could not find button containing {needle!r}"
    return matches[0]


def _submit_low_workload_run(app):
    element_by_label(app.number_input, "Simulations").set_value(200)
    element_by_label(app.number_input, "Seed").set_value(123)
    _button_by_label_contains(app, "Run Monte Carlo Simulation").click().run(timeout=120)
    assert not app.exception
    return app


def test_smart_scenario_generate_apply_reset_commands_do_not_crash():
    app = run_app_once()

    element_by_label(app.selectbox, "Scenario profile").set_value("Downside")
    element_by_label(app.number_input, "Generator seed").set_value(42)
    _button_by_label_contains(app, "Generate Plausible Scenario").click().run(timeout=60)
    assert not app.exception
    visible_text = all_visible_text(app)
    assert "Pending smart scenario ready" in visible_text

    _button_by_label_contains(app, "Apply Generated Scenario").click().run(timeout=60)
    assert not app.exception
    number_values = {element.label: element.value for element in app.number_input}
    assert number_values["Initial Occupancy (%)"] <= 83.0

    _button_by_label_contains(app, "Reset to Base Inputs").click().run(timeout=60)
    assert not app.exception
    number_values = {element.label: element.value for element in app.number_input}
    assert number_values["Initial Occupancy (%)"] == 82.6
    assert_no_unsafe_visible_phrases(all_visible_text(app))


def test_low_workload_run_command_reveals_results_exports_and_ai_prompt_surface():
    app = _submit_low_workload_run(run_app_once())
    visible_text = all_visible_text(app)

    assert "Simulation Results" in values(app.header)
    assert "Exports" in visible_text
    assert "Audit Evidence" in visible_text
    assert "Available Downloads:" in visible_text
    assert "Download simulation results, metrics summary, and input parameters" in visible_text

    for prompt in (
        "Explain these results in simple business terms",
        "What are the main risks?",
        "Why are the returns strong?",
        "What should I review before trusting this scenario?",
    ):
        assert prompt in labels(app.button)

    _button_by_label_contains(app, "Why are the returns strong?").click().run(timeout=60)
    assert not app.exception
    prompt_text = all_visible_text(app)
    assert "Boundary" in prompt_text
    assert "not investment advice" in prompt_text.lower()
    assert_no_unsafe_visible_phrases(prompt_text)


def test_analysis_build_and_download_controls_have_visible_contracts():
    app = run_app_once()
    buttons = labels(app.button)

    assert "Build Heatmap 1" in buttons
    assert "Build Model-Derived Tornado" in buttons
    assert "Build Heatmap 2" in buttons
    assert "Simulations per cell" in labels(app.slider)
    assert "Simulations per cell (Heatmap 2)" in labels(app.slider)
    assert "Tornado simulations per case" in labels(app.number_input)

    # Streamlit AppTest does not expose browser download handling. The contract
    # here is the visible affordance after a low-workload run, not file download IO.
    app = _submit_low_workload_run(app)
    assert "Available Downloads:" in all_visible_text(app)
    assert_no_unsafe_visible_phrases(all_visible_text(app))
