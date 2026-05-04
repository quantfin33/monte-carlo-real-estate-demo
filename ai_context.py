from __future__ import annotations

import math
from typing import Any

import pandas as pd

from number_sanity import build_number_sanity_report


NON_CLAIMS = [
    "not investment advice",
    "not production-ready",
    "not a fully validated financial product",
    "no live ERP/Odoo/MCP integration",
]


def _finite_series(df: pd.DataFrame, candidates: list[str]) -> tuple[str | None, pd.Series]:
    if df is None or not hasattr(df, "columns"):
        return None, pd.Series(dtype=float)

    empty_source: str | None = None
    for column in candidates:
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            empty_source = column
            continue
        finite = series[series.map(lambda value: math.isfinite(float(value)))]
        if finite.empty:
            empty_source = column
            continue
        return column, finite.astype(float)

    return empty_source, pd.Series(dtype=float)


def _round_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return round(numeric, 6)


def _metric_context(
    df: pd.DataFrame,
    name: str,
    candidates: list[str],
    *,
    unit: str,
    include_tail: bool = False,
) -> tuple[dict[str, Any], str | None]:
    source_column, series = _finite_series(df, candidates)
    metric: dict[str, Any] = {
        "available": False,
        "source_column": source_column,
        "unit": unit,
    }

    if source_column is None:
        return metric, f"{name} is not available in current context."
    if series.empty:
        return metric, f"{name} has no finite values in current context."

    metric["available"] = True
    metric["p50"] = _round_or_none(series.quantile(0.50))
    if include_tail:
        metric["p5"] = _round_or_none(series.quantile(0.05))
        metric["p95"] = _round_or_none(series.quantile(0.95))
    return metric, None


def _build_risk_flags(core_metrics: dict[str, dict[str, Any]]) -> list[str]:
    flags: list[str] = []

    irr = core_metrics.get("irr", {})
    if irr.get("available") and irr.get("p5") is not None and float(irr["p5"]) < 0:
        flags.append("IRR downside includes negative scenarios at P5.")

    dscr = core_metrics.get("dscr", {})
    if dscr.get("available") and dscr.get("p50") is not None and float(dscr["p50"]) < 1.20:
        flags.append("Median DSCR is below 1.20x, so coverage risk is visible in the current output.")

    debt_yield = core_metrics.get("debt_yield", {})
    if debt_yield.get("available") and debt_yield.get("p50") is not None and float(debt_yield["p50"]) < 0.08:
        flags.append("Median debt yield is below 8.0%, so lender-yield sensitivity is visible.")

    ltv = core_metrics.get("ltv", {})
    if ltv.get("available") and ltv.get("p50") is not None and float(ltv["p50"]) > 0.70:
        flags.append("Median LTV is above 70.0%, so leverage risk is visible.")

    if not flags:
        flags.append("No threshold-based risk flags were triggered from the supported metrics.")
    return flags


def _trace_context(trace_payload: Any) -> dict[str, Any]:
    if not isinstance(trace_payload, dict):
        return {
            "available": False,
            "summary": "Trace payload is not available in current context.",
        }

    trace_cashflows = trace_payload.get("trace_cashflows") or {}
    trace_summary = trace_payload.get("trace_summary") or {}
    consistency = trace_cashflows.get("consistency_check") or {}
    cash_flow_series = trace_cashflows.get("cash_flow_series") or []

    return {
        "available": True,
        "mode": trace_summary.get("mode"),
        "run_index": trace_summary.get("run_index"),
        "cash_flow_count": trace_summary.get("cash_flow_count") or len(cash_flow_series),
        "engine_irr": _round_or_none(trace_cashflows.get("engine_irr") or trace_summary.get("irr")),
        "computed_irr": _round_or_none(trace_cashflows.get("computed_irr")),
        "consistency_passed": consistency.get("passed"),
        "replay_matches_selected": trace_summary.get("replay_matches_selected"),
    }


def _sensitivity_context(payload: Any, *, label: str) -> dict[str, Any]:
    if payload is None:
        return {
            "available": False,
            "label": label,
            "summary": f"{label} is not available in current context.",
        }

    if isinstance(payload, dict):
        available = bool(payload.get("available", payload))
        summary = payload.get("summary") if isinstance(payload.get("summary"), str) else None
        return {
            "available": available,
            "label": payload.get("label", label),
            "summary": summary or f"{label} metadata is available in current context.",
        }

    if not hasattr(payload, "columns"):
        return {
            "available": False,
            "label": label,
            "summary": f"{label} is not available in current context.",
        }

    df = payload
    if df.empty:
        return {
            "available": False,
            "label": label,
            "row_count": 0,
            "summary": f"{label} is empty in current context.",
        }

    context: dict[str, Any] = {
        "available": True,
        "label": label,
        "row_count": int(len(df)),
        "columns": [str(column) for column in df.columns],
    }

    if "IRR_pct" in df.columns:
        irr_pct = pd.to_numeric(df["IRR_pct"], errors="coerce").dropna()
        if not irr_pct.empty:
            context["irr_pct_min"] = _round_or_none(float(irr_pct.min()))
            context["irr_pct_max"] = _round_or_none(float(irr_pct.max()))
            context["irr_pct_mean"] = _round_or_none(float(irr_pct.mean()))

    tornado_cols = {"parameter", "low_delta", "high_delta"}
    if tornado_cols.issubset(set(df.columns)):
        deltas = pd.to_numeric(df[["low_delta", "high_delta"]].stack(), errors="coerce").dropna()
        if not deltas.empty:
            context["max_abs_delta"] = _round_or_none(float(deltas.abs().max()))

    context["summary"] = f"{label} metadata is available as a directional sensitivity surface."
    return context


def build_ai_context(
    df: pd.DataFrame,
    trace_payload: dict[str, Any] | None = None,
    selected_scenario: str | None = None,
    heatmap_1: Any | None = None,
    heatmap_2: Any | None = None,
    tornado: Any | None = None,
) -> dict[str, Any]:
    """Build a compact, deterministic context for the optional analyst chat."""

    if df is None or not hasattr(df, "columns"):
        df = pd.DataFrame()

    metric_specs = {
        "irr": (["IRR"], "decimal_rate", True),
        "npv": (["NPV"], "dollars", False),
        "cash_on_cash": (["CoC", "CashOnCash"], "decimal_rate", False),
        "equity_multiple": (["EquityMultiple", "Equity_Multiple"], "multiple", False),
        "dscr": (["DSCR", "DSCR_Y1", "MinDSCR", "DSCR_Min"], "ratio", False),
        "debt_yield": (["DebtYield_Y1", "DebtYield", "MinDebtYield", "DebtYield_Min"], "decimal_rate", False),
        "ltv": (["LTV"], "decimal_rate", False),
        "exit_cap": (["ExitCap", "ExitCapRate"], "decimal_rate", False),
    }

    warnings: list[str] = []
    core_metrics: dict[str, dict[str, Any]] = {}
    for metric_name, (candidates, unit, include_tail) in metric_specs.items():
        metric, warning = _metric_context(
            df,
            metric_name,
            candidates,
            unit=unit,
            include_tail=include_tail,
        )
        core_metrics[metric_name] = metric
        if warning:
            warnings.append(warning)

    supporting_metric_specs = {
        "initial_occupancy": (["_Debug_InitialOccupancy", "InitialOccupancy", "initial_occupancy"], "decimal_rate"),
        "physical_occupancy": (["PhysicalOccupancyRate"], "decimal_rate"),
        "economic_occupancy": (["EconomicOccupancyRate"], "decimal_rate"),
        "prepay_cost_total": (["Prepay_Cost_Total"], "dollars"),
        "defeasance_cost_refi": (["Defeasance_Cost_Refi"], "dollars"),
        "prepay_cost_sale": (["Prepay_Cost_Sale"], "dollars"),
    }
    supporting_metrics: dict[str, dict[str, Any]] = {}
    for metric_name, (candidates, unit) in supporting_metric_specs.items():
        metric, _warning = _metric_context(
            df,
            metric_name,
            candidates,
            unit=unit,
        )
        supporting_metrics[metric_name] = metric

    context = {
        "project_status": {
            "visual_demo_ready": True,
            "annual_model_core_validated": True,
            "demo_local_review_only": True,
            "broader_validation_incomplete": True,
            "hosted_release": False,
        },
        "scenario": {
            "name": selected_scenario or "Current simulation",
        },
        "simulation": {
            "row_count": int(len(df)),
        },
        "core_metrics": core_metrics,
        "supporting_metrics": supporting_metrics,
        "risk_flags": _build_risk_flags(core_metrics),
        "trace": _trace_context(trace_payload),
        "sensitivity": {
            "heatmap_1": _sensitivity_context(heatmap_1, label="Heatmap 1"),
            "heatmap_2": _sensitivity_context(heatmap_2, label="Heatmap 2"),
            "tornado": _sensitivity_context(tornado, label="Tornado"),
        },
        "warnings": warnings,
        "non_claims": list(NON_CLAIMS),
    }
    context["number_sanity_report"] = build_number_sanity_report(context)
    return context
