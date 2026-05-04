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

    assert "What the model shows" in answer
    assert "IRR" in answer
    assert "not investment advice" in answer


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
    assert "Risk readout" in answer


def test_missing_requested_metric_is_called_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What is the DSCR and trace cash flow?", _context_with_missing_trace())

    assert "dscr is not available in current context" in answer.lower()
    assert "trace detail is not available in current context" in answer.lower()


def test_missing_requested_supporting_metric_is_called_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What is the physical occupancy?", _context_with_missing_trace())

    assert "physical_occupancy is not available in current context" in answer.lower()


def test_fallback_includes_sanity_review_caveats(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Why are the returns strong?", _strong_context()).lower()

    assert "number sanity readout" in answer
    assert "p50 irr is above 15%" in answer
    assert "what to review" in answer
    assert "lease-up" in answer
    assert "defeasance" in answer


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
