from __future__ import annotations

from tests.ui_app_helpers import (
    all_visible_text,
    assert_no_unsafe_visible_phrases,
    labels,
    run_app_once,
    values,
)


def test_default_app_render_exposes_core_public_controls() -> None:
    app = run_app_once()

    number_inputs = labels(app.number_input)
    selectboxes = labels(app.selectbox)
    checkboxes = labels(app.checkbox)
    sliders = labels(app.slider)
    buttons = labels(app.button)
    expanders = labels(app.expander)
    headers = values(app.header)

    for label in [
        "Simulations",
        "Seed",
        "In-place Rent ($/RSF/YR)",
        "Total RSF",
        "Initial Occupancy (%)",
        "Market Rent ($/RSF/YR)",
        "Purchase Price ($)",
        "Operating Expenses Start ($)",
    ]:
        assert label in number_inputs

    for label in [
        "Answer style",
        "Scenario profile",
        "Scenario",
        "Tax Mode",
        "Recovery Type",
        "Prepayment Method",
        "Reserve Policy",
    ]:
        assert label in selectboxes

    for label in [
        "Enable Exit Cap Rate Override",
        "Enable Latent Market Strength",
        "Enable Stage 2 Correlations",
        "Vacancy Auto-Lease",
        "Monitor Debt Covenants",
        "Enable Refinance Rules",
    ]:
        assert label in checkboxes

    assert "Backfill Probability (per-month)" in sliders
    assert "Generate Plausible Scenario" in buttons
    assert "Apply Generated Scenario" in buttons
    assert "Reset to Base Inputs" in buttons
    assert any("Run Monte Carlo Simulation" in label for label in buttons)
    assert "Developer status" in expanders
    assert "Advanced lease-up controls — parked / future validation" in expanders
    assert "Simulation Controls" in headers
    assert "AI Analyst" in headers


def test_default_visible_surface_keeps_public_claim_boundary() -> None:
    app = run_app_once()
    text = all_visible_text(app)

    assert_no_unsafe_visible_phrases(text)
    assert "investment advice" not in text.lower() or "not investment advice" in text.lower()
    assert "live ERP/Odoo" not in text or "not live ERP/Odoo" in text
