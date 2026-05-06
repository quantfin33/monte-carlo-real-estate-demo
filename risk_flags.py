from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskFlag:
    severity: str
    category: str
    message: str
    metric: str
    threshold: float
    observed_value: float
    evidence_source: str
    status: str = "OPEN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_THRESHOLDS = {
    "dscr_min": 1.25,
    "debt_yield_min": 0.08,
    "ltv_max": 0.65,
    "irr_p5_floor": 0.05,
    "cashflow_min": 0.0,
    "irr_spread_max": 0.30,
}


def generate_risk_flags(
    df: pd.DataFrame,
    *,
    thresholds: dict[str, float] | None = None,
    evidence_source: str = "simulation_results",
) -> list[dict[str, Any]]:
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    flags: list[RiskFlag] = []

    dscr = _min_from_candidates(df, ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr", "DSCR"])
    if dscr is not None and dscr < limits["dscr_min"]:
        flags.append(
            _flag(
                severity="HIGH" if dscr < 1.0 else "MEDIUM",
                category="covenant",
                message="Minimum DSCR is below the demo threshold.",
                metric="DSCR",
                threshold=limits["dscr_min"],
                observed_value=dscr,
                evidence_source=evidence_source,
            )
        )

    debt_yield = _min_from_candidates(df, ["MinDebtYield", "DebtYield_Min", "DebtYield_Y1"])
    if debt_yield is not None and debt_yield < limits["debt_yield_min"]:
        flags.append(
            _flag(
                severity="HIGH" if debt_yield < 0.06 else "MEDIUM",
                category="covenant",
                message="Minimum debt yield is below the demo threshold.",
                metric="DebtYield",
                threshold=limits["debt_yield_min"],
                observed_value=debt_yield,
                evidence_source=evidence_source,
            )
        )

    ltv = _max_from_candidates(df, ["LTV_Max", "LTV"])
    if ltv is not None and ltv > limits["ltv_max"]:
        flags.append(
            _flag(
                severity="HIGH" if ltv > 0.75 else "MEDIUM",
                category="leverage",
                message="Maximum LTV is above the demo threshold.",
                metric="LTV",
                threshold=limits["ltv_max"],
                observed_value=ltv,
                evidence_source=evidence_source,
            )
        )

    irr = _series(df, "IRR")
    if not irr.empty:
        irr_p5 = float(np.percentile(irr, 5))
        if irr_p5 < limits["irr_p5_floor"]:
            flags.append(
                _flag(
                    severity="HIGH" if irr_p5 < 0 else "MEDIUM",
                    category="downside",
                    message="Downside IRR percentile is below the demo floor.",
                    metric="IRR_P5",
                    threshold=limits["irr_p5_floor"],
                    observed_value=irr_p5,
                    evidence_source=evidence_source,
                )
            )

        irr_spread = float(np.percentile(irr, 95) - np.percentile(irr, 5))
        if irr_spread > limits["irr_spread_max"]:
            flags.append(
                _flag(
                    severity="MEDIUM",
                    category="volatility",
                    message="IRR distribution spread is above the demo volatility threshold.",
                    metric="IRR_P95_P5_SPREAD",
                    threshold=limits["irr_spread_max"],
                    observed_value=irr_spread,
                    evidence_source=evidence_source,
                )
            )

    cashflow = _first_series(df, ["NetCashFlow", "NetCashFlow_Y1", "CashFlow", "CashFlow_Y1"])
    if cashflow is not None and not cashflow.empty:
        min_cashflow = float(cashflow.min())
        if min_cashflow < limits["cashflow_min"]:
            flags.append(
                _flag(
                    severity="MEDIUM",
                    category="cashflow",
                    message="At least one sampled cashflow is negative.",
                    metric="NetCashFlow",
                    threshold=limits["cashflow_min"],
                    observed_value=min_cashflow,
                    evidence_source=evidence_source,
                )
            )

    return [flag.to_dict() for flag in flags]


def _flag(
    *,
    severity: str,
    category: str,
    message: str,
    metric: str,
    threshold: float,
    observed_value: float,
    evidence_source: str,
) -> RiskFlag:
    return RiskFlag(
        severity=severity,
        category=category,
        message=message,
        metric=metric,
        threshold=float(threshold),
        observed_value=float(observed_value),
        evidence_source=evidence_source,
    )


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()


def _first_series(df: pd.DataFrame, columns: list[str]) -> pd.Series | None:
    for column in columns:
        series = _series(df, column)
        if not series.empty:
            return series
    return None


def _min_from_candidates(df: pd.DataFrame, columns: list[str]) -> float | None:
    series = _first_series(df, columns)
    return float(series.min()) if series is not None and not series.empty else None


def _max_from_candidates(df: pd.DataFrame, columns: list[str]) -> float | None:
    series = _first_series(df, columns)
    return float(series.max()) if series is not None and not series.empty else None

