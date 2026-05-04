from __future__ import annotations

import pandas as pd

from ai_context import build_ai_context


def _sample_results() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "IRR": [0.08, 0.10, 0.12, 0.14, 0.16],
            "NPV": [100_000, 200_000, 300_000, 400_000, 500_000],
            "CoC": [0.04, 0.05, 0.06, 0.07, 0.08],
            "EquityMultiple": [1.20, 1.30, 1.40, 1.50, 1.60],
            "DSCR_Y1": [1.10, 1.15, 1.20, 1.25, 1.30],
            "DebtYield_Y1": [0.07, 0.08, 0.09, 0.10, 0.11],
            "LTV": [0.55, 0.58, 0.60, 0.62, 0.65],
            "ExitCap": [0.075, 0.08, 0.085, 0.09, 0.095],
            "_Debug_InitialOccupancy": [0.826, 0.826, 0.826, 0.826, 0.826],
            "PhysicalOccupancyRate": [0.96, 0.97, 0.98, 0.99, 1.00],
            "EconomicOccupancyRate": [0.95, 0.96, 0.97, 0.98, 0.99],
            "Prepay_Cost_Total": [0, 250_000, 500_000, 750_000, 1_000_000],
            "Defeasance_Cost_Refi": [0, 0, 400_000, 600_000, 800_000],
            "Prepay_Cost_Sale": [0, 100_000, 200_000, 300_000, 400_000],
        }
    )


def test_ai_context_builds_supported_metrics():
    context = build_ai_context(_sample_results(), selected_scenario="Base")

    assert context["scenario"]["name"] == "Base"
    assert context["simulation"]["row_count"] == 5
    assert context["project_status"]["visual_demo_ready"] is True
    assert context["project_status"]["hosted_release"] is False

    metrics = context["core_metrics"]
    assert metrics["irr"]["available"] is True
    assert {"p5", "p50", "p95"}.issubset(metrics["irr"])
    assert metrics["npv"]["p50"] == 300_000.0
    assert metrics["cash_on_cash"]["p50"] == 0.06
    assert metrics["equity_multiple"]["p50"] == 1.4
    assert metrics["dscr"]["p50"] == 1.2
    assert metrics["debt_yield"]["p50"] == 0.09
    assert metrics["ltv"]["p50"] == 0.6
    assert metrics["exit_cap"]["p50"] == 0.085

    supporting = context["supporting_metrics"]
    assert supporting["initial_occupancy"]["p50"] == 0.826
    assert supporting["physical_occupancy"]["p50"] == 0.98
    assert supporting["economic_occupancy"]["p50"] == 0.97
    assert supporting["prepay_cost_total"]["p50"] == 500_000.0
    assert supporting["defeasance_cost_refi"]["p50"] == 400_000.0
    assert supporting["prepay_cost_sale"]["p50"] == 200_000.0


def test_ai_context_includes_number_sanity_report():
    context = build_ai_context(_sample_results(), selected_scenario="Base")

    assert "number_sanity_report" in context
    report = context["number_sanity_report"]
    assert "headline_assessment" in report
    assert "review_flags" in report
    assert "caveats" in report
    assert "non_claims" in report


def test_ai_context_missing_metrics_warn_without_crashing():
    context = build_ai_context(pd.DataFrame({"IRR": [0.10, 0.12, 0.14]}))

    assert context["core_metrics"]["irr"]["available"] is True
    assert context["core_metrics"]["npv"]["available"] is False
    assert any("npv is not available in current context" in warning for warning in context["warnings"])
    assert any("dscr is not available in current context" in warning for warning in context["warnings"])
    assert "number_sanity_report" in context
    assert "core.npv" in context["number_sanity_report"]["unavailable_or_placeholder_metrics"]
    assert context["trace"]["available"] is False
    assert (
        context["trace"]["summary"]
        == "Trace engine support exists, but this chat context does not currently include the selected-run trace bundle."
    )
    assert context["sensitivity"]["heatmap_1"]["tool_available"] is True
    assert context["sensitivity"]["heatmap_1"]["built_in_current_session"] is False
    assert context["sensitivity"]["heatmap_1"]["available"] is False
    assert (
        "tool is available for directional review"
        in context["sensitivity"]["heatmap_1"]["summary"]
    )
    assert (
        "no generated chart context is currently included"
        in context["sensitivity"]["heatmap_1"]["summary"]
    )


def test_ai_context_includes_non_claims():
    context = build_ai_context(_sample_results())
    non_claims = "\n".join(context["non_claims"])

    assert "not investment advice" in non_claims
    assert "not production-ready" in non_claims
    assert "not a fully validated financial product" in non_claims
    assert "no live ERP/Odoo/MCP/SAP integration" in non_claims


def test_ai_context_summarizes_optional_trace_payload():
    trace_payload = {
        "trace_summary": {
            "mode": "median",
            "run_index": 12,
            "cash_flow_count": 6,
            "replay_matches_selected": True,
        },
        "trace_cashflows": {
            "engine_irr": 0.12,
            "computed_irr": 0.1200001,
            "consistency_check": {"passed": True},
            "cash_flow_series": [-100, 20, 25, 30, 35, 140],
        },
    }

    context = build_ai_context(_sample_results(), trace_payload=trace_payload)

    assert context["trace"]["available"] is True
    assert context["trace"]["run_index"] == 12
    assert context["trace"]["cash_flow_count"] == 6
    assert context["trace"]["engine_irr"] == 0.12
    assert context["trace"]["computed_irr"] == 0.12
    assert context["trace"]["consistency_passed"] is True
    assert "Trace/Explain context is available" in context["trace"]["summary"]


def test_ai_context_accepts_compact_trace_payload():
    trace_payload = {
        "available": True,
        "summary": "Trace/Explain context is available for the selected run; cash-flow count and IRR recompute status are included.",
        "mode": "p50_trace",
        "run_index": 7,
        "cash_flow_count": 6,
        "engine_irr": 0.143,
        "computed_irr": 0.1430001,
        "consistency_passed": True,
        "replay_matches_selected": True,
    }

    context = build_ai_context(_sample_results(), trace_payload=trace_payload)

    assert context["trace"]["available"] is True
    assert context["trace"]["mode"] == "p50_trace"
    assert context["trace"]["run_index"] == 7
    assert context["trace"]["cash_flow_count"] == 6
    assert context["trace"]["engine_irr"] == 0.143
    assert context["trace"]["computed_irr"] == 0.143
    assert context["trace"]["consistency_passed"] is True


def test_ai_context_summarizes_optional_sensitivity_payloads():
    heatmap_1 = pd.DataFrame(
        {
            "ExitCap": [0.075, 0.080],
            "RentGrowth": [0.02, 0.03],
            "IRR_pct": [16.5, 17.2],
        }
    )
    tornado = pd.DataFrame(
        {
            "parameter": ["Exit Cap", "Rent Growth"],
            "low_case": ["low", "low"],
            "high_case": ["high", "high"],
            "low_delta": [-0.01, -0.02],
            "high_delta": [0.02, 0.03],
            "abs_impact": [0.02, 0.03],
        }
    )

    context = build_ai_context(
        _sample_results(),
        heatmap_1=heatmap_1,
        tornado=tornado,
    )

    assert context["sensitivity"]["heatmap_1"]["available"] is True
    assert context["sensitivity"]["heatmap_1"]["tool_available"] is True
    assert context["sensitivity"]["heatmap_1"]["built_in_current_session"] is True
    assert context["sensitivity"]["heatmap_1"]["row_count"] == 2
    assert context["sensitivity"]["tornado"]["available"] is True
    assert context["sensitivity"]["tornado"]["built_in_current_session"] is True
    assert context["sensitivity"]["tornado"]["max_abs_delta"] == 0.03
    assert any(
        "directional scenario surfaces" in caveat
        for caveat in context["number_sanity_report"]["caveats"]
    )
