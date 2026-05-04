from __future__ import annotations

import builtins

import pandas as pd

import ai_analyst
from ai_context import build_ai_context


def _context_with_missing_trace() -> dict:
    df = pd.DataFrame(
        {
            "IRR": [0.08, 0.10, 0.12, 0.14, 0.16],
            "NPV": [100_000, 200_000, 300_000, 400_000, 500_000],
            "CoC": [0.04, 0.05, 0.06, 0.07, 0.08],
            "EquityMultiple": [1.20, 1.30, 1.40, 1.50, 1.60],
        }
    )
    return build_ai_context(df, selected_scenario="Base")


def _strong_context() -> dict:
    df = pd.DataFrame(
        {
            "IRR": [0.15, 0.16, 0.1732, 0.19, 0.21],
            "NPV": [20_000_000, 30_000_000, 35_460_000, 40_000_000, 50_000_000],
            "CoC": [0.12, 0.14, 0.1599, 0.18, 0.20],
            "EquityMultiple": [2.0, 2.2, 2.31, 2.4, 2.6],
            "DSCR_Y1": [3.8, 4.0, 4.39, 4.5, 4.8],
            "DebtYield_Y1": [0.25, 0.27, 0.2966, 0.31, 0.34],
            "_Debug_InitialOccupancy": [0.826, 0.826, 0.826, 0.826, 0.826],
            "PhysicalOccupancyRate": [0.99, 0.998, 0.9988, 0.999, 1.0],
            "EconomicOccupancyRate": [0.99, 0.995, 1.0, 1.0, 1.0],
            "Defeasance_Cost_Refi": [1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000],
            "Prepay_Cost_Sale": [500_000, 700_000, 900_000, 1_100_000, 1_300_000],
        }
    )
    return build_ai_context(df, selected_scenario="Base")


def test_fallback_answer_works_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Explain the headline metrics.", _context_with_missing_trace())

    assert "Short answer" in answer
    assert "Key numbers" in answer
    assert "IRR" in answer
    assert "not investment advice" in answer.lower()
    assert "Not production-ready" in answer
    assert "No live ERP/Odoo/MCP/SAP integration" in answer


def test_no_openai_import_is_attempted_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "openai":
            raise AssertionError("openai should not be imported without OPENAI_API_KEY")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    answer = ai_analyst.answer_question("What is the IRR?", _context_with_missing_trace())

    assert "IRR" in answer


def test_investment_advice_request_is_refused(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Should I invest in this deal?", _context_with_missing_trace())

    assert "can’t provide investment advice" in answer
    assert "transaction recommendation" in answer
    assert "Boundary" in answer


def test_missing_requested_metric_is_called_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What is the DSCR and trace cash flow?", _context_with_missing_trace())

    assert "DSCR is not available in current context" in answer
    assert "Trace engine support exists" in answer
    assert "does not currently include the selected-run trace bundle" in answer


def test_missing_requested_supporting_metric_is_called_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What is the physical occupancy?", _context_with_missing_trace())

    assert "Hold-average occupancy is not available in current context" in answer


def test_fallback_includes_sanity_review_caveats(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Why are the returns strong?", _strong_context())
    answer_lower = answer.lower()

    assert "Review flags" in answer
    assert "High returns need assumptions review" in answer
    assert "$35.5M" in answer
    assert "17.32%" in answer
    assert "29.66%" in answer
    assert "prepay/defeasance" in answer_lower
    assert "hold-average occupancy" in answer
    assert "initial_occupancy" not in answer
    assert "prepay_cost_total" not in answer
    assert "DebtYield" not in answer


def test_short_fallback_formats_values_for_presentation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Explain these results.", _strong_context())

    assert "- IRR P50: 17.32%" in answer
    assert "- NPV P50: $35.5M" in answer
    assert "- Cash-on-Cash P50: 15.99%" in answer
    assert "- Equity Multiple P50: 2.31x" in answer
    assert "- DSCR: 4.39x" in answer
    assert "- Debt Yield: 29.66%" in answer


def test_trace_present_can_be_mentioned(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    trace_payload = {
        "available": True,
        "summary": "Trace/Explain context is available for the selected run; cash-flow count and IRR recompute status are included.",
        "mode": "p50_trace",
        "run_index": 12,
        "cash_flow_count": 6,
        "engine_irr": 0.1732,
        "computed_irr": 0.1732,
        "consistency_passed": True,
        "replay_matches_selected": True,
    }
    df = pd.DataFrame({"IRR": [0.16, 0.1732, 0.19], "NPV": [30_000_000, 35_460_000, 40_000_000]})
    context = build_ai_context(df, trace_payload=trace_payload)

    answer = ai_analyst.answer_question("Explain the trace cash flow.", context)

    assert "Trace/Explain context is available for the selected run" in answer
    assert "cash-flow count: 6" in answer
    assert "IRR recompute passed: True" in answer


def test_unbuilt_sensitivity_tools_are_described_honestly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What does the heatmap show?", _context_with_missing_trace())

    assert "Sensitivity tools are available for directional review" in answer
    assert "no generated chart context is currently included" in answer
    assert "are available as directional scenario surfaces" not in answer


def test_built_sensitivity_context_is_directional_only(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    heatmap_1 = pd.DataFrame(
        {
            "ExitCap": [0.075, 0.080],
            "RentGrowth": [0.02, 0.03],
            "IRR_pct": [16.5, 17.2],
        }
    )
    context = build_ai_context(_strong_context_dataframe(), heatmap_1=heatmap_1)

    answer = ai_analyst.answer_question("What does the heatmap show?", context)

    assert "Heatmap 1" in answer
    assert "directional scenario surfaces" in answer
    assert "proof of full model correctness" in answer


def test_investment_advice_phrase_is_refused(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Can I use this as investment advice?", _strong_context())

    assert "can’t provide investment advice" in answer
    assert "transaction recommendation" in answer


def test_fallback_answer_avoids_forbidden_positive_claims(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Can you summarize this dashboard?", _strong_context()).lower()

    forbidden_positive_claims = [
        "this is production-ready",
        "is production-ready",
        "is a fully validated financial product",
        "odoo integration is implemented",
        "erp integration is implemented",
        "mcp server is implemented",
        "deployed erp workflow",
        "autonomous investment advice",
    ]
    for phrase in forbidden_positive_claims:
        assert phrase not in answer


def _strong_context_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "IRR": [0.15, 0.16, 0.1732, 0.19, 0.21],
            "NPV": [20_000_000, 30_000_000, 35_460_000, 40_000_000, 50_000_000],
            "CoC": [0.12, 0.14, 0.1599, 0.18, 0.20],
            "EquityMultiple": [2.0, 2.2, 2.31, 2.4, 2.6],
        }
    )
