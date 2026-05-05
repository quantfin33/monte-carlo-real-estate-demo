from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

import ai_analyst
import scenario_randomizer
from ai_context import build_ai_context


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "UI.py"


def _run_initial_app(monkeypatch) -> AppTest:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=60)
    assert not app.exception
    return app


def _labels(elements) -> list[str]:
    return [str(getattr(element, "label", "")) for element in elements]


def _values(elements) -> list[str]:
    values: list[str] = []
    for element in elements:
        for attr in ("value", "body", "label", "placeholder"):
            value = getattr(element, attr, None)
            if value:
                values.append(str(value))
                break
    return values


def _all_visible_text(app: AppTest) -> str:
    text: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "info",
        "warning",
        "success",
        "metric",
        "chat_message",
    ):
        text.extend(_values(getattr(app, attr, [])))
    return "\n".join(text)


def _element_by_label(elements, label: str):
    matches = [element for element in elements if getattr(element, "label", None) == label]
    assert matches, f"Could not find Streamlit widget labeled {label!r}"
    return matches[0]


def _submit_low_workload_base_run(app: AppTest) -> AppTest:
    _element_by_label(app.number_input, "Simulations").set_value(200)
    _element_by_label(app.number_input, "Seed").set_value(123)
    run_buttons = [button for button in app.button if "Run Monte Carlo Simulation" in button.label]
    assert run_buttons, "Run Monte Carlo Simulation button was not exposed by AppTest"
    run_buttons[0].click().run(timeout=120)
    assert not app.exception
    return app


def test_initial_render_exposes_reviewer_visible_controls(monkeypatch):
    app = _run_initial_app(monkeypatch)

    number_inputs = _labels(app.number_input)
    selectboxes = _labels(app.selectbox)
    checkboxes = _labels(app.checkbox)
    sliders = _labels(app.slider)
    buttons = _labels(app.button)
    expanders = _labels(app.expander)
    headers = _values(app.header)

    assert "Scenario profile" in selectboxes
    assert "Generator seed" in number_inputs
    assert "Generate Plausible Scenario" in buttons
    assert "Apply Generated Scenario" in buttons
    assert "Reset to Base Inputs" in buttons

    for label in [
        "Simulations",
        "Seed",
        "In-place Rent ($/RSF/YR)",
        "Total RSF",
        "Initial Occupancy (%)",
        "Purchase Price ($)",
    ]:
        assert label in number_inputs

    assert "Scenario" in selectboxes
    assert "Answer style" in selectboxes
    assert "Vacancy Auto-Lease" in checkboxes
    assert "Enable Refinance Rules" in checkboxes
    assert "Backfill Probability (per-month)" in sliders
    assert any("Run Monte Carlo Simulation" in label for label in buttons)
    assert "Build Heatmap 1" in buttons
    assert "Build Model-Derived Tornado" in buttons
    assert "Build Heatmap 2" in buttons
    assert "Developer status" in expanders
    assert "Advanced lease-up controls — parked / future validation" in expanders
    assert "Simulation Controls" in headers
    assert "AI Analyst" in headers
    assert "Trace / Explain P50 IRR" in headers


def test_smart_scenario_generate_apply_reset_and_run(monkeypatch):
    app = _run_initial_app(monkeypatch)

    _element_by_label(app.selectbox, "Scenario profile").set_value("Downside")
    _element_by_label(app.number_input, "Generator seed").set_value(42)
    _element_by_label(app.button, "Generate Plausible Scenario").click().run(timeout=60)
    assert not app.exception

    visible_text = _all_visible_text(app)
    assert "Pending smart scenario ready" in visible_text
    assert scenario_randomizer.CAVEAT in visible_text
    assert "Simulation Results" not in _values(app.header)
    assert len(app.dataframe) >= 1

    _element_by_label(app.button, "Apply Generated Scenario").click().run(timeout=60)
    assert not app.exception
    values_after_apply = {element.label: element.value for element in app.number_input}
    assert values_after_apply["Initial Occupancy (%)"] <= 83.0
    assert values_after_apply["Market Rent Growth Max (%)"] <= 2.0

    _submit_low_workload_base_run(app)
    assert "Simulation Results" in _values(app.header)

    _element_by_label(app.button, "Reset to Base Inputs").click().run(timeout=60)
    assert not app.exception
    values_after_reset = {element.label: element.value for element in app.number_input}
    assert values_after_reset["Initial Occupancy (%)"] == 82.6
    assert values_after_reset["Market Rent Growth Min (%)"] == 2.0


def test_main_submit_reveals_results_ai_trace_and_export_surfaces(monkeypatch):
    app = _submit_low_workload_base_run(_run_initial_app(monkeypatch))

    headers = _values(app.header)
    subheaders = _values(app.subheader)
    expanders = _labels(app.expander)
    buttons = _labels(app.button)
    visible_text = _all_visible_text(app)

    assert "Simulation Results" in headers
    assert "AI Analyst" in headers
    assert "Trace / Explain P50 IRR" in headers
    assert "Exports" in visible_text
    assert "Audit Evidence" in visible_text
    assert "Key IRR Metrics" in subheaders
    assert "Additional KPIs" in subheaders
    assert "Risk & Covenants — Detailed Percentiles" in expanders
    assert "Parked metrics not included in current contract" in expanders
    assert "Trace surface status" in expanders
    assert "Demo analyst mode is active" in visible_text
    assert "Download simulation results, metrics summary, and input parameters" in visible_text

    for prompt in [
        "Explain these results in simple business terms",
        "What are the main risks?",
        "Why are the returns strong?",
        "What should I review before trusting this scenario?",
    ]:
        assert prompt in buttons


def test_ai_quick_prompt_uses_demo_fallback_path(monkeypatch):
    app = _submit_low_workload_base_run(_run_initial_app(monkeypatch))

    _element_by_label(app.button, "Why are the returns strong?").click().run(timeout=60)
    assert not app.exception

    visible_text = _all_visible_text(app)
    assert "Short answer" in visible_text
    assert "Key numbers" in visible_text
    assert "Review flags" in visible_text
    assert "Boundary" in visible_text
    assert "not investment advice" in visible_text.lower()


def test_investment_advice_refusal_uses_existing_ai_path(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    context = build_ai_context(
        pd.DataFrame(
            {
                "IRR": [0.15, 0.17, 0.19],
                "NPV": [20_000_000, 35_000_000, 45_000_000],
                "CoC": [0.12, 0.15, 0.18],
                "EquityMultiple": [2.0, 2.3, 2.6],
            }
        ),
        selected_scenario="Base",
    )

    answer = ai_analyst.answer_question("Should I invest in this deal?", context)

    assert "can’t provide investment advice" in answer
    assert "transaction recommendation" in answer
    assert "Boundary" in answer


def test_downloads_and_heavy_side_options_are_visible_but_not_browser_verified(monkeypatch):
    app = _submit_low_workload_base_run(_run_initial_app(monkeypatch))
    visible_text = _all_visible_text(app)
    buttons = _labels(app.button)
    metrics = _labels(app.metric)

    assert "Build Heatmap 1" in buttons
    assert "Build Model-Derived Tornado" in buttons
    assert "Build Heatmap 2" in buttons
    assert "Available Downloads:" in visible_text
    assert "Audit Evidence" in visible_text
    assert "Latest Audit Run" in metrics
    assert "Audit Status" in metrics
    assert "Failed Tie-Outs" in metrics

    # Streamlit AppTest does not expose st.download_button as a convenience list.
    # Browser-level download behavior remains a separate optional Playwright/manual pass.
    assert not hasattr(app, "download_button")
