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


def test_fallback_answer_works_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Explain the headline metrics.", _context_with_missing_trace())

    assert "Headline metrics" in answer
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
    assert "buy/sell/invest recommendations" in answer
    assert "Risk readout" in answer


def test_missing_requested_metric_is_called_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("What is the DSCR and trace cash flow?", _context_with_missing_trace())

    assert "dscr is not available in current context" in answer.lower()
    assert "trace detail is not available in current context" in answer.lower()


def test_fallback_answer_avoids_forbidden_positive_claims(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    answer = ai_analyst.answer_question("Can you summarize this dashboard?", _context_with_missing_trace()).lower()

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
