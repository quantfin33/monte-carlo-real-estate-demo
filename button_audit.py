from __future__ import annotations

import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_TOLERANCE = 0.005


def _finite_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    series = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return series.dropna()


def _percentile(df: pd.DataFrame, column: str, percentile: float) -> float:
    series = _finite_series(df, column)
    if series.empty:
        return float("nan")
    return float(np.percentile(series, percentile))


def _mean(df: pd.DataFrame, column: str) -> float:
    series = _finite_series(df, column)
    if series.empty:
        return float("nan")
    return float(series.mean())


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "button"


def compare_metric(
    displayed: float,
    recomputed: float,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    scale: str = "native",
    metric: str,
    formula: str,
    severity_if_fail: str = "P2",
    raw_value: float | None = None,
    notes: str = "",
) -> dict[str, Any]:
    displayed_value = float(displayed) if _is_finite(displayed) else float("nan")
    recomputed_value = float(recomputed) if _is_finite(recomputed) else float("nan")
    raw_metric_value = recomputed_value if raw_value is None else raw_value

    if _is_finite(displayed_value) and _is_finite(recomputed_value):
        delta = displayed_value - recomputed_value
        passed = abs(delta) <= tolerance
    elif not _is_finite(displayed_value) and not _is_finite(recomputed_value):
        delta = 0.0
        passed = True
    else:
        delta = float("nan")
        passed = False

    return {
        "metric": metric,
        "displayed_value": displayed_value,
        "raw_value": raw_metric_value,
        "recomputed_value": recomputed_value,
        "formula": formula,
        "scale": scale,
        "tolerance": tolerance,
        "delta": delta,
        "pass": bool(passed),
        "severity": "" if passed else severity_if_fail,
        "notes": notes,
    }


def _metric_row(
    metric: str,
    value: float,
    *,
    formula: str,
    scale: str = "native",
    tolerance: float = DEFAULT_TOLERANCE,
    severity_if_fail: str = "P2",
) -> dict[str, Any]:
    return compare_metric(
        value,
        value,
        tolerance=tolerance,
        scale=scale,
        metric=metric,
        formula=formula,
        severity_if_fail=severity_if_fail,
    )


def recompute_main_metrics(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        _metric_row("Row Count", float(len(df)), formula="len(results)", scale="count", tolerance=0.0),
    ]

    for label, column, factor in [
        ("IRR", "IRR", 100.0),
        ("NPV", "NPV", 1.0),
        ("Cash-on-Cash", "CoC", 100.0),
        ("Equity Multiple", "EquityMultiple", 1.0),
    ]:
        for suffix, percentile in [("P5", 5), ("P50", 50), ("P95", 95)]:
            rows.append(
                _metric_row(
                    f"{label} {suffix}",
                    _percentile(df, column, percentile) * factor,
                    formula=f"p{percentile}({column})" + (" * 100" if factor == 100.0 else ""),
                    scale="percent_points" if factor == 100.0 else "native",
                    severity_if_fail="P1" if label in {"IRR", "NPV"} else "P2",
                )
            )
        rows.append(
            _metric_row(
                f"{label} Mean",
                _mean(df, column) * factor,
                formula=f"mean({column})" + (" * 100" if factor == 100.0 else ""),
                scale="percent_points" if factor == 100.0 else "native",
            )
        )

    if "PI" in df.columns:
        pi_series = _finite_series(df, "PI")
    elif {"NPV", "Equity"}.issubset(df.columns):
        equity = pd.to_numeric(df["Equity"], errors="coerce")
        npv = pd.to_numeric(df["NPV"], errors="coerce")
        pi_series = ((npv + equity) / equity).replace([np.inf, -np.inf], np.nan).dropna()
    else:
        pi_series = pd.Series(dtype=float)

    if pi_series.empty:
        pi_p50 = float("nan")
    else:
        pi_p50 = float(np.percentile(pi_series, 50))
    rows.append(_metric_row("PI P50", pi_p50, formula="p50((NPV + Equity) / Equity)"))

    optional_specs = [
        ("DSCR P50", "DSCR", "p50(DSCR)", "ratio"),
        ("Debt Yield P50", "DebtYield_Y1", "p50(DebtYield_Y1) * 100", "percent_points"),
        ("Yield on Cost P50", "YieldOnCost", "p50(YieldOnCost) * 100", "percent_points"),
        ("Cap Rate P50", "CapRate", "p50(CapRate) * 100", "percent_points"),
        ("LTV P50", "LTV", "p50(LTV) * 100", "percent_points"),
        ("Break-Even Occupancy P50", "BreakEvenOcc", "p50(BreakEvenOcc) * 100", "percent_points"),
        ("Physical Occupancy P50", "PhysicalOccupancyRate", "p50(PhysicalOccupancyRate) * 100", "percent_points"),
        ("Economic Occupancy P50", "EconomicOccupancyRate", "p50(EconomicOccupancyRate) * 100", "percent_points"),
        ("Prepay Sale Cost Mean", "Prepay_Cost_Sale", "mean(Prepay_Cost_Sale)", "native"),
    ]
    for metric, column, formula, scale in optional_specs:
        factor = 100.0 if scale == "percent_points" and column != "DSCR" else 1.0
        rows.append(_metric_row(metric, _percentile(df, column, 50) * factor, formula=formula, scale=scale))

    return rows


def recompute_heatmap_metrics(df: pd.DataFrame) -> list[dict[str, Any]]:
    irr_pct = _finite_series(df, "IRR_pct")
    if irr_pct.empty:
        minimum = maximum = value_range = top_cell = float("nan")
    else:
        minimum = float(irr_pct.min())
        maximum = float(irr_pct.max())
        value_range = maximum - minimum
        top_cell = maximum

    return [
        _metric_row("Heatmap Row Count", float(len(df)), formula="len(heatmap)", scale="count", tolerance=0.0),
        _metric_row("Heatmap Min IRR", minimum, formula="min(IRR_pct)", scale="percent_points"),
        _metric_row("Heatmap Max IRR", maximum, formula="max(IRR_pct)", scale="percent_points"),
        _metric_row("Heatmap Range", value_range, formula="max(IRR_pct) - min(IRR_pct)", scale="percent_points"),
        _metric_row("Heatmap Top Cell IRR", top_cell, formula="IRR_pct at max cell", scale="percent_points"),
    ]


def recompute_tornado_metrics(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, item in df.iterrows():
        parameter = str(item.get("parameter", "Unknown"))
        base_metric = float(item.get("base_metric", float("nan")))
        low_metric = float(item.get("low_metric", float("nan")))
        high_metric = float(item.get("high_metric", float("nan")))
        expected_low_delta = low_metric - base_metric
        expected_high_delta = high_metric - base_metric
        rows.append(
            compare_metric(
                float(item.get("low_delta", float("nan"))),
                expected_low_delta,
                tolerance=1e-9,
                scale="native_delta",
                metric=f"Tornado {parameter} Low Delta",
                formula="low_metric - base_metric",
                severity_if_fail="P1",
            )
        )
        rows.append(
            compare_metric(
                float(item.get("high_delta", float("nan"))),
                expected_high_delta,
                tolerance=1e-9,
                scale="native_delta",
                metric=f"Tornado {parameter} High Delta",
                formula="high_metric - base_metric",
                severity_if_fail="P1",
            )
        )
    return rows


def _normalise_metric_rows(recomputed_metrics: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(recomputed_metrics, dict):
        return [_metric_row(str(metric), float(value), formula="provided summary metric") for metric, value in recomputed_metrics.items()]
    return [dict(row) for row in recomputed_metrics]


def record_button_run(
    button_name: str,
    input_snapshot: dict[str, Any],
    output_df: pd.DataFrame,
    displayed_metrics: dict[str, Any],
    recomputed_metrics: list[dict[str, Any]] | dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    run_id = f"{_slugify(button_name)}_{timestamp}_{uuid.uuid4().hex[:8]}"
    slug = _slugify(button_name)
    latest_raw_csv = output_path / f"latest_{slug}_raw.csv"
    output_df.to_csv(latest_raw_csv, index=False)

    metric_rows = _normalise_metric_rows(recomputed_metrics)
    final_rows: list[dict[str, Any]] = []
    for row in metric_rows:
        metric_name = str(row.get("metric", "Unnamed Metric"))
        if metric_name in displayed_metrics:
            row = compare_metric(
                float(displayed_metrics[metric_name]),
                float(row.get("recomputed_value", float("nan"))),
                tolerance=float(row.get("tolerance", DEFAULT_TOLERANCE)),
                scale=str(row.get("scale", "native")),
                metric=metric_name,
                formula=str(row.get("formula", "recomputed metric")),
                severity_if_fail=str(row.get("severity") or row.get("severity_if_fail") or "P2"),
                raw_value=row.get("raw_value"),
                notes=str(row.get("notes", "")),
            )

        final_rows.append(
            {
                "run_id": run_id,
                "timestamp": timestamp,
                "button_name": button_name,
                **row,
            }
        )

    tieouts = pd.DataFrame(final_rows)
    failed = tieouts[tieouts["pass"].astype(str).str.lower() != "true"] if not tieouts.empty else pd.DataFrame()
    p1_count = int((failed.get("severity", pd.Series(dtype=str)) == "P1").sum()) if not failed.empty else 0
    p2_count = int((failed.get("severity", pd.Series(dtype=str)) == "P2").sum()) if not failed.empty else 0
    status = "PASS" if failed.empty else "FAIL"

    summary = {
        "run_id": run_id,
        "timestamp": timestamp,
        "button_name": button_name,
        "status": status,
        "row_count": int(len(output_df)),
        "metric_count": int(len(tieouts)),
        "failed_count": int(len(failed)),
        "p1_count": p1_count,
        "p2_count": p2_count,
        "input_json": json.dumps(input_snapshot, sort_keys=True, default=str),
        "raw_csv": str(latest_raw_csv),
        "latest_raw_csv": str(latest_raw_csv),
        "notes": "",
    }

    button_runs_path = output_path / "button_runs.csv"
    metric_tieouts_path = output_path / "metric_tieouts.csv"
    _append_csv(button_runs_path, pd.DataFrame([summary]))
    _append_csv(metric_tieouts_path, tieouts)
    return summary


def _append_csv(path: Path, frame: pd.DataFrame) -> None:
    if path.exists():
        existing = pd.read_csv(path)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(path, index=False)
