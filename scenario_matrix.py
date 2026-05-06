from __future__ import annotations

from itertools import product
from typing import Any, Callable

import pandas as pd

import monte_carlo_model
from export_contracts import NON_CLAIMS, extract_headline_metrics, source_metadata, to_jsonable, utc_now_iso


Runner = Callable[[dict[str, Any], int, int], pd.DataFrame]

STATE_PROBABILITIES = {
    "DOWN": 0.25,
    "BASE": 0.50,
    "UP": 0.25,
}

RENT_GROWTH_STATES = {
    "DOWN": 0.00,
    "BASE": 0.03,
    "UP": 0.05,
}

EXPENSE_GROWTH_STATES = {
    "DOWN": 0.05,
    "BASE": 0.03,
    "UP": 0.02,
}

EXIT_CAP_STATES = {
    "DOWN": 0.090,
    "BASE": 0.085,
    "UP": 0.0825,
}


def build_27_case_matrix(
    *,
    base_params: dict[str, Any] | None = None,
    seed: int,
    sims_per_case: int = 10,
    runner: Runner | None = None,
) -> list[dict[str, Any]]:
    matrix_runner = runner or _default_runner
    base = dict(base_params or monte_carlo_model.default_params())
    rows: list[dict[str, Any]] = []

    for index, (rent_state, expense_state, exit_state) in enumerate(
        product(RENT_GROWTH_STATES, EXPENSE_GROWTH_STATES, EXIT_CAP_STATES),
        start=1,
    ):
        case_seed = int(seed) + index * 1009
        params = _scenario_params(base, rent_state, expense_state, exit_state)
        df = matrix_runner(params, int(sims_per_case), case_seed)
        metrics = extract_headline_metrics(df)
        probability = (
            STATE_PROBABILITIES[rent_state]
            * STATE_PROBABILITIES[expense_state]
            * STATE_PROBABILITIES[exit_state]
        )
        rows.append(
            to_jsonable(
                {
                    "case_number": index,
                    "scenario_id": f"S-{rent_state}-{expense_state}-{exit_state}",
                    "rent_growth_state": rent_state,
                    "expense_growth_state": expense_state,
                    "exit_cap_state": exit_state,
                    "rent_growth": RENT_GROWTH_STATES[rent_state],
                    "expense_growth": EXPENSE_GROWTH_STATES[expense_state],
                    "exit_cap": EXIT_CAP_STATES[exit_state],
                    "probability": probability,
                    "seed": case_seed,
                    "sims": int(sims_per_case),
                    "metrics": metrics,
                }
            )
        )

    return rows


def build_scenario_matrix_export(
    matrix: list[dict[str, Any]],
    *,
    seed: int,
    inputs: dict[str, Any],
    sims_per_case: int,
    preset: str = "unspecified",
) -> dict[str, Any]:
    return to_jsonable(
        {
            "contract_name": "scenario_matrix",
            "contract_version": "1.0",
            "source": source_metadata("scenario_matrix"),
            "generated_at_utc": utc_now_iso(),
            "label": "demo_sensitivity_not_forecast_or_advice",
            "seed": int(seed),
            "preset": preset,
            "inputs": inputs,
            "sims_per_case": int(sims_per_case),
            "matrix": matrix,
            "base_case_id": "S-BASE-BASE-BASE",
            "probabilities_sum": float(sum(row["probability"] for row in matrix)),
            "non_claims": NON_CLAIMS,
            "network_calls_made": False,
        }
    )


def matrix_to_dataframe(matrix: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in matrix:
        metrics = row.get("metrics", {})
        risk = metrics.get("risk", {}) if isinstance(metrics, dict) else {}
        rows.append(
            {
                "case_number": row["case_number"],
                "scenario_id": row["scenario_id"],
                "rent_growth_state": row["rent_growth_state"],
                "expense_growth_state": row["expense_growth_state"],
                "exit_cap_state": row["exit_cap_state"],
                "rent_growth": row["rent_growth"],
                "expense_growth": row["expense_growth"],
                "exit_cap": row["exit_cap"],
                "probability": row["probability"],
                "seed": row["seed"],
                "sims": row["sims"],
                "irr_mean": _nested_metric(metrics, "irr", "mean"),
                "irr_p5": _nested_metric(metrics, "irr", "p5"),
                "irr_p50": _nested_metric(metrics, "irr", "p50"),
                "irr_p95": _nested_metric(metrics, "irr", "p95"),
                "npv_mean": _nested_metric(metrics, "npv", "mean"),
                "coc_mean": _nested_metric(metrics, "coc", "mean"),
                "equity_multiple_mean": _nested_metric(metrics, "equity_multiple", "mean"),
                "min_dscr": risk.get("min_dscr"),
                "min_debt_yield": risk.get("min_debt_yield"),
                "max_ltv": risk.get("max_ltv"),
            }
        )
    return pd.DataFrame(rows)


def _default_runner(params: dict[str, Any], n: int, seed: int) -> pd.DataFrame:
    return monte_carlo_model.run_simulation(n=n, seed=seed, params=params, parallel=False)


def _scenario_params(base: dict[str, Any], rent_state: str, expense_state: str, exit_state: str) -> dict[str, Any]:
    params = dict(base)
    rent_growth = RENT_GROWTH_STATES[rent_state]
    params.update(
        {
            "market_rent_growth_min": rent_growth,
            "market_rent_growth_max": rent_growth,
            "opex_growth_rate": EXPENSE_GROWTH_STATES[expense_state],
            "exit_cap_override": EXIT_CAP_STATES[exit_state],
        }
    )
    return params


def _nested_metric(metrics: dict[str, Any], group: str, field: str) -> float | None:
    value = metrics.get(group, {}).get(field)
    return float(value) if value is not None else None
