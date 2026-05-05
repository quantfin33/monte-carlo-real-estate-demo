#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "integration_demo" / "sample_business_summary.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import monte_carlo_model  # noqa: E402


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _values_for_columns(df: Any, column_names: Iterable[str]) -> list[float]:
    for column_name in column_names:
        if column_name not in df.columns:
            continue
        values = [_as_float(value) for value in df[column_name].tolist()]
        return [value for value in values if value is not None]
    return []


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]

    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _metric_percentiles(df: Any, column_names: Iterable[str], percentiles: tuple[int, ...]) -> dict[str, float]:
    values = _values_for_columns(df, column_names)
    summary: dict[str, float] = {}
    for percentile in percentiles:
        value = _percentile(values, percentile)
        if value is not None:
            summary[f"p{percentile}"] = value
    return summary


def _risk_flags(metrics: dict[str, dict[str, float]]) -> list[str]:
    flags: list[str] = []

    irr_p50 = metrics.get("irr", {}).get("p50")
    if irr_p50 is not None:
        flags.append(
            "Median IRR is above the 15% dashboard reference threshold."
            if irr_p50 >= 0.15
            else "Median IRR is below the 15% dashboard reference threshold."
        )

    dscr_p50 = metrics.get("dscr", {}).get("p50")
    if dscr_p50 is not None:
        flags.append(
            "Median DSCR is above the 1.25x lender-style reference threshold."
            if dscr_p50 >= 1.25
            else "Median DSCR is below the 1.25x lender-style reference threshold."
        )

    debt_yield_p50 = metrics.get("debt_yield", {}).get("p50")
    if debt_yield_p50 is not None:
        flags.append(
            "Median debt yield is above the 8% lender-style reference threshold."
            if debt_yield_p50 >= 0.08
            else "Median debt yield is below the 8% lender-style reference threshold."
        )

    ltv_p50 = metrics.get("ltv", {}).get("p50")
    if ltv_p50 is not None:
        flags.append(
            "Median LTV is within the 65% reference threshold."
            if ltv_p50 <= 0.65
            else "Median LTV is above the 65% reference threshold."
        )

    return flags


def build_business_summary_payload(
    simulation_count: int = 500,
    seed: int = 12345,
    generated_at: str | None = None,
) -> dict[str, Any]:
    params = monte_carlo_model.default_params()
    df = monte_carlo_model.run_simulation(n=simulation_count, seed=seed, params=params, parallel=False)

    core_metrics = {
        "irr": _metric_percentiles(df, ("IRR",), (5, 50, 95)),
        "npv": _metric_percentiles(df, ("NPV",), (50,)),
        "cash_on_cash": _metric_percentiles(df, ("CoC",), (50,)),
        "equity_multiple": _metric_percentiles(df, ("EquityMultiple",), (50,)),
        "dscr": _metric_percentiles(df, ("DSCR_Y1", "DSCR"), (50,)),
        "debt_yield": _metric_percentiles(df, ("DebtYield_Y1", "MinDebtYield", "DebtYield_Min"), (50,)),
        "ltv": _metric_percentiles(df, ("LTV", "LTV_Max"), (50,)),
        "exit_cap": _metric_percentiles(df, ("ExitCap",), (50,)),
    }

    return {
        "generated_at": generated_at or _utc_timestamp(),
        "package_metadata": {
            "name": "monte-carlo-real-estate-demo",
            "artifact_type": "local deterministic business-summary export",
            "source": "monte_carlo_model.run_simulation",
            "simulation_count": int(simulation_count),
            "seed": int(seed),
        },
        "scenario": {
            "name": "Base demo scenario",
            "description": "Default annual-model assumptions exported for local portfolio review.",
        },
        "core_metrics": core_metrics,
        "risk_flags": _risk_flags(core_metrics),
        "validation_boundary": {
            "visual_demo_ready": True,
            "annual_model_core_validated": True,
            "live_erp_integration": False,
            "live_odoo_integration": False,
            "live_crm_integration": False,
            "live_sap_integration": False,
            "live_mcp_server": False,
            "openai_agent_integration": False,
            "hosted_release": False,
        },
        "intended_future_targets": [
            "reporting",
            "API wrapper",
            "MCP tool layer",
            "ERP/Odoo handoff",
        ],
        "non_claims": [
            "Live Odoo integration is not included.",
            "Live ERP, CRM, or SAP integration is not included.",
            "A live MCP server is not included.",
            "Hosted deployment is not included.",
            "Autonomous investment advice is not included.",
        ],
    }


def write_business_summary(
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    simulation_count: int = 500,
    seed: int = 12345,
    generated_at: str | None = None,
) -> Path:
    payload = build_business_summary_payload(
        simulation_count=simulation_count,
        seed=seed,
        generated_at=generated_at,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    output_path = write_business_summary()
    print(f"Wrote {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
