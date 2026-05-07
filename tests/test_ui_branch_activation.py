from __future__ import annotations

from tests.ui_app_helpers import (
    all_visible_text,
    assert_no_unsafe_visible_phrases,
    element_by_label,
    labels,
    rerun_app,
    run_app_once,
)


def _set_checkbox(app, label: str, value: bool = True):
    element_by_label(app.checkbox, label).set_value(value)
    return rerun_app(app)


def _set_selectbox(app, label: str, value: str):
    element_by_label(app.selectbox, label).set_value(value)
    return rerun_app(app)


def _assert_no_unsafe_surface(app) -> None:
    assert_no_unsafe_visible_phrases(all_visible_text(app))


def test_market_and_correlation_branches_activate_without_exception():
    app = run_app_once()

    app = _set_checkbox(app, "Enable Exit Cap Rate Override")
    assert "Exit Cap Rate Override (%)" in labels(app.number_input)

    app = _set_checkbox(app, "Enable Latent Market Strength")
    number_labels = labels(app.number_input)
    for expected in (
        "Correlation (ρ)",
        "Occupancy Std Dev (%)",
        "Growth Tilt (bps)",
        "Min Occupancy",
        "Max Occupancy",
        "Seed Offset",
    ):
        assert expected in number_labels

    app = _set_checkbox(app, "Enable Stage 2 Correlations")
    assert "Correlation Variables" in labels(app.multiselect)
    assert "Corr Seed Offset" in labels(app.number_input)
    _assert_no_unsafe_surface(app)


def test_debt_covenant_and_refinance_branches_activate_without_exception():
    app = run_app_once()

    app = _set_checkbox(app, "Monitor Debt Covenants")
    assert "Violation Response" in labels(app.selectbox)
    for expected in (
        "Minimum DSCR",
        "Minimum Debt Yield (%)",
        "Maximum LTV (%)",
    ):
        assert expected in labels(app.number_input)

    app = _set_checkbox(app, "Enable Refinance Rules")
    for expected in (
        "Refinance Lockout (Years)",
        "Maximum LTV for Refi (%)",
        "Minimum DSCR for Refi",
        "Minimum Debt Yield for Refi (%)",
    ):
        assert expected in labels(app.number_input)
    _assert_no_unsafe_surface(app)


def test_prepayment_method_branches_activate_without_exception():
    app = _set_selectbox(run_app_once(), "Prepayment Method", "stepdown")
    for expected in (
        "Year 1 Rate (%)",
        "Year 2 Rate (%)",
        "Year 3 Rate (%)",
        "Year 4 Rate (%)",
        "Year 5 Rate (%)",
    ):
        assert expected in labels(app.number_input)

    app = _set_selectbox(run_app_once(), "Prepayment Method", "ym")
    assert "Yield Maintenance Spread (%)" in labels(app.number_input)

    app = _set_selectbox(run_app_once(), "Prepayment Method", "defeasance")
    assert "Open Year (Optional)" in labels(app.number_input)
    assert "Discount Method" in labels(app.selectbox)
    assert "Risk-Free Rate (%)" in labels(app.number_input)

    app = _set_selectbox(app, "Discount Method", "curve")
    for expected in (
        "Year 1 (%)",
        "Year 2 (%)",
        "Year 3 (%)",
        "Year 4 (%)",
        "Year 5 (%)",
    ):
        assert expected in labels(app.number_input)
    _assert_no_unsafe_surface(app)


def test_policy_option_branches_render_without_exception():
    app = run_app_once()

    for label, options in (
        ("Tax Mode", ("independent", "rent_indexed")),
        ("Recovery Type", ("NNN", "CAM_CAP", "BASE_YEAR")),
        ("Payment Frequency", ("annual", "monthly")),
        ("Reserve Policy", ("accrue_only", "offset_building")),
    ):
        for option in options:
            app = _set_selectbox(app, label, option)

    _assert_no_unsafe_surface(app)


def test_analysis_and_ai_branch_controls_are_visible_without_heavy_commands():
    app = run_app_once()

    assert "Simulations per cell" in labels(app.slider)
    assert "Simulations per cell (Heatmap 2)" in labels(app.slider)
    assert "Build Heatmap 1" in labels(app.button)
    assert "Build Heatmap 2" in labels(app.button)

    for expected in (
        "Tornado simulations per case",
        "Tornado metric",
        "Tornado statistic",
        "Build Model-Derived Tornado",
    ):
        visible = labels(app.number_input) + labels(app.selectbox) + labels(app.button)
        assert expected in visible

    assert "AI Analyst" in all_visible_text(app)
    _assert_no_unsafe_surface(app)
