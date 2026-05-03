from __future__ import annotations

import json
import os
import re
from typing import Any


DEFAULT_MODEL = "gpt-5-mini"

SYSTEM_INSTRUCTIONS = """
You are a business analytics assistant for a local Streamlit Monte Carlo real-estate dashboard.
Answer only from the provided JSON context. Do not invent missing metrics, traces, charts, or validation evidence.
If a requested value is absent, say "not available in current context".
Do not provide investment advice, buy/sell/invest recommendations, or autonomous decision guidance.
Use bounded claims: this is demo/local review, not a production deployment, not a fully validated financial product,
and it has no live MCP, Odoo, ERP, CRM, or SAP integration.
Keep the answer concise and business-facing.
""".strip()

ADVICE_RE = re.compile(
    r"\b(should\s+(i|we)\s+(buy|sell|invest)|recommend\s+(buying|selling|investing)|"
    r"is\s+this\s+a\s+good\s+investment|investment\s+recommendation)\b",
    re.IGNORECASE,
)

REQUESTED_METRICS = {
    "irr": ("irr", "return"),
    "npv": ("npv", "net present value"),
    "cash_on_cash": ("cash-on-cash", "cash on cash", "coc"),
    "equity_multiple": ("equity multiple",),
    "dscr": ("dscr", "coverage"),
    "debt_yield": ("debt yield",),
    "ltv": ("ltv", "loan-to-value", "loan to value"),
    "exit_cap": ("exit cap", "exitcap"),
    "cap_rate": ("cap rate", "caprate"),
    "trace": ("trace", "explain", "cash flow", "cashflow"),
}


def has_live_openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def answer_question(question: str, context: dict[str, Any]) -> str:
    """Answer a dashboard question with optional live OpenAI mode and safe fallback."""

    if has_live_openai_configured():
        live_answer = _answer_with_openai(question, context)
        if live_answer:
            return live_answer

    return _fallback_answer(question, context)


def _answer_with_openai(question: str, context: dict[str, Any]) -> str | None:
    try:
        from openai import OpenAI
    except Exception:
        return None

    try:
        client = OpenAI()
        if not hasattr(client, "responses"):
            return None
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=SYSTEM_INSTRUCTIONS,
            input=_build_prompt(question, context),
        )
        text = getattr(response, "output_text", None)
        if text:
            return str(text).strip()
    except Exception:
        return None
    return None


def _build_prompt(question: str, context: dict[str, Any]) -> str:
    return (
        "Question:\n"
        f"{question.strip()}\n\n"
        "Current dashboard context JSON:\n"
        f"{json.dumps(context, sort_keys=True, default=str)}"
    )


def _fallback_answer(question: str, context: dict[str, Any]) -> str:
    question_text = (question or "").strip()
    sections: list[str] = []

    if ADVICE_RE.search(question_text):
        sections.append(
            "I can’t provide investment advice or buy/sell/invest recommendations. "
            "I can explain the current simulation outputs, visible risks, and missing data boundaries."
        )

    missing_notes = _requested_missing_notes(question_text, context)
    metric_summary = _metric_summary(context)
    if metric_summary:
        sections.append(metric_summary)

    risk_summary = _risk_summary(context)
    if risk_summary:
        sections.append(risk_summary)

    if missing_notes:
        sections.append("Missing data: " + " ".join(missing_notes))

    trace_note = _trace_summary(question_text, context)
    if trace_note:
        sections.append(trace_note)

    sections.append(
        "Boundary: this answer is grounded in the current dashboard context. "
        "It is not investment advice, not production-ready, not a fully validated financial product, "
        "and it does not claim live ERP/Odoo/MCP integration."
    )

    return "\n\n".join(sections)


def _metric_summary(context: dict[str, Any]) -> str:
    metrics = context.get("core_metrics", {})
    parts = []

    irr = metrics.get("irr", {})
    if irr.get("available"):
        parts.append(
            "IRR shows P5/P50/P95 of "
            f"{_format_value(irr.get('p5'), irr.get('unit'))}, "
            f"{_format_value(irr.get('p50'), irr.get('unit'))}, and "
            f"{_format_value(irr.get('p95'), irr.get('unit'))}."
        )

    for label, key in [
        ("NPV P50", "npv"),
        ("Cash-on-Cash P50", "cash_on_cash"),
        ("Equity Multiple P50", "equity_multiple"),
        ("DSCR P50", "dscr"),
        ("Debt Yield P50", "debt_yield"),
        ("LTV P50", "ltv"),
        ("Exit Cap P50", "exit_cap"),
    ]:
        metric = metrics.get(key, {})
        if metric.get("available"):
            parts.append(f"{label} is {_format_value(metric.get('p50'), metric.get('unit'))}.")

    if not parts:
        return "No supported headline metrics are available in current context."
    return "Headline metrics: " + " ".join(parts)


def _risk_summary(context: dict[str, Any]) -> str:
    risk_flags = context.get("risk_flags") or []
    if not risk_flags:
        return ""
    return "Risk readout: " + " ".join(str(flag) for flag in risk_flags)


def _trace_summary(question: str, context: dict[str, Any]) -> str:
    lower = question.lower()
    if not any(token in lower for token in REQUESTED_METRICS["trace"]):
        return ""

    trace = context.get("trace", {})
    if not trace.get("available"):
        return "Trace detail is not available in current context."

    pieces = [
        f"Trace run index: {trace.get('run_index')}",
        f"cash-flow count: {trace.get('cash_flow_count')}",
    ]
    if trace.get("engine_irr") is not None:
        pieces.append(f"engine IRR: {_format_value(trace.get('engine_irr'), 'decimal_rate')}")
    if trace.get("computed_irr") is not None:
        pieces.append(f"computed IRR: {_format_value(trace.get('computed_irr'), 'decimal_rate')}")
    return "Trace summary: " + "; ".join(pieces) + "."


def _requested_missing_notes(question: str, context: dict[str, Any]) -> list[str]:
    lower = question.lower()
    metrics = context.get("core_metrics", {})
    notes: list[str] = []

    for metric_name, aliases in REQUESTED_METRICS.items():
        if metric_name == "trace":
            continue
        if not any(alias in lower for alias in aliases):
            continue
        metric = metrics.get(metric_name)
        if not metric or not metric.get("available"):
            notes.append(f"{metric_name} is not available in current context.")

    if any(alias in lower for alias in REQUESTED_METRICS["trace"]):
        trace = context.get("trace", {})
        if not trace.get("available"):
            notes.append("trace detail is not available in current context.")

    return notes


def _format_value(value: Any, unit: str | None) -> str:
    if value is None:
        return "not available in current context"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "not available in current context"

    if unit == "decimal_rate":
        return f"{numeric * 100:.2f}%"
    if unit == "dollars":
        return f"${numeric:,.0f}"
    if unit == "multiple":
        return f"{numeric:.2f}x"
    if unit == "ratio":
        return f"{numeric:.2f}x"
    return f"{numeric:,.2f}"
