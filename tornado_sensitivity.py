from __future__ import annotations

from copy import deepcopy
from typing import Callable

import numpy as np
import pandas as pd

import rmc_model


Runner = Callable[[dict, int, int], pd.DataFrame]


def _default_runner(params: dict, n: int, seed: int) -> pd.DataFrame:
    return rmc_model.run_simulation(n=n, seed=seed, params=params, parallel=False)


def _metric_value(df: pd.DataFrame, metric: str, stat: str) -> float:
    if metric not in df.columns:
        return float("nan")
    series = pd.to_numeric(df[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return float("nan")
    if stat == "mean":
        return float(series.mean())
    if stat == "p5":
        return float(np.percentile(series, 5))
    if stat == "p95":
        return float(np.percentile(series, 95))
    return float(np.percentile(series, 50))


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _set_rent_growth(params: dict, delta: float) -> None:
    params["market_rent_growth_min"] = float(params.get("market_rent_growth_min", 0.02)) + delta
    params["market_rent_growth_max"] = float(params.get("market_rent_growth_max", 0.04)) + delta


def _scenario_definitions(params: dict) -> list[dict]:
    interest_rate = float(params.get("interest_rate", 0.0675))
    exit_cap = float(params.get("exit_cap_override", params.get("exit_cap_mode", 0.085)))
    rent_min = float(params.get("market_rent_growth_min", 0.02))
    rent_max = float(params.get("market_rent_growth_max", 0.04))
    occupancy = float(params.get("initial_occupancy", 0.826))
    purchase_price = float(params.get("purchase_price", 108_000_000.0))
    opex = float(params.get("operating_expenses_start", 2_500_000.0))

    return [
        {
            "parameter": "Interest Rate",
            "low_case": _format_percent(interest_rate - 0.01),
            "high_case": _format_percent(interest_rate + 0.01),
            "low": lambda p: p.update({"interest_rate": interest_rate - 0.01}),
            "high": lambda p: p.update({"interest_rate": interest_rate + 0.01}),
        },
        {
            "parameter": "Exit Cap",
            "low_case": _format_percent(exit_cap - 0.01),
            "high_case": _format_percent(exit_cap + 0.01),
            "low": lambda p: p.update({"exit_cap_override": exit_cap - 0.01}),
            "high": lambda p: p.update({"exit_cap_override": exit_cap + 0.01}),
        },
        {
            "parameter": "Rent Growth",
            "low_case": f"{_format_percent(rent_min - 0.01)} to {_format_percent(rent_max - 0.01)}",
            "high_case": f"{_format_percent(rent_min + 0.01)} to {_format_percent(rent_max + 0.01)}",
            "low": lambda p: _set_rent_growth(p, -0.01),
            "high": lambda p: _set_rent_growth(p, 0.01),
        },
        {
            "parameter": "Initial Occupancy",
            "low_case": _format_percent(max(0.0, occupancy - 0.05)),
            "high_case": _format_percent(min(1.0, occupancy + 0.05)),
            "low": lambda p: p.update({"initial_occupancy": max(0.0, occupancy - 0.05)}),
            "high": lambda p: p.update({"initial_occupancy": min(1.0, occupancy + 0.05)}),
        },
        {
            "parameter": "Purchase Price",
            "low_case": f"${purchase_price * 0.95:,.0f}",
            "high_case": f"${purchase_price * 1.05:,.0f}",
            "low": lambda p: p.update({"purchase_price": purchase_price * 0.95}),
            "high": lambda p: p.update({"purchase_price": purchase_price * 1.05}),
        },
        {
            "parameter": "Operating Expenses",
            "low_case": f"${opex * 0.90:,.0f}",
            "high_case": f"${opex * 1.10:,.0f}",
            "low": lambda p: p.update({"operating_expenses_start": opex * 0.90}),
            "high": lambda p: p.update({"operating_expenses_start": opex * 1.10}),
        },
    ]


def build_tornado_sensitivity_data(
    params: dict,
    *,
    n_per_case: int = 250,
    seed: int = 123,
    metric: str = "IRR",
    stat: str = "p50",
    runner: Runner | None = None,
) -> pd.DataFrame:
    run = runner or _default_runner
    base_params = deepcopy(params)
    base_df = run(base_params, int(n_per_case), int(seed))
    base_metric = _metric_value(base_df, metric, stat)

    rows: list[dict] = []
    for scenario in _scenario_definitions(base_params):
        low_params = deepcopy(base_params)
        high_params = deepcopy(base_params)
        scenario["low"](low_params)
        scenario["high"](high_params)

        low_metric = _metric_value(run(low_params, int(n_per_case), int(seed)), metric, stat)
        high_metric = _metric_value(run(high_params, int(n_per_case), int(seed)), metric, stat)
        low_delta = low_metric - base_metric
        high_delta = high_metric - base_metric

        rows.append(
            {
                "parameter": scenario["parameter"],
                "low_case": scenario["low_case"],
                "high_case": scenario["high_case"],
                "base_metric": base_metric,
                "low_metric": low_metric,
                "high_metric": high_metric,
                "low_delta": low_delta,
                "high_delta": high_delta,
                "abs_impact": max(abs(low_delta), abs(high_delta)),
                "status": "model-derived",
            }
        )

    return pd.DataFrame(rows).sort_values("abs_impact", ascending=False).reset_index(drop=True)
