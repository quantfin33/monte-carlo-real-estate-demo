from __future__ import annotations

import math

import pandas as pd

from tornado_sensitivity import build_tornado_sensitivity_data


def test_tornado_sensitivity_is_model_derived() -> None:
    calls: list[dict[str, float]] = []
    params = {
        "interest_rate": 0.0675,
        "exit_cap_mode": 0.085,
        "market_rent_growth_min": 0.02,
        "market_rent_growth_max": 0.04,
        "initial_occupancy": 0.826,
        "purchase_price": 108_000_000.0,
        "operating_expenses_start": 2_500_000.0,
    }

    def fake_runner(run_params: dict, n: int, seed: int) -> pd.DataFrame:
        calls.append(dict(run_params))
        exit_cap = run_params.get("exit_cap_override", run_params.get("exit_cap_mode", 0.085))
        value = (
            0.18
            - 0.90 * run_params["interest_rate"]
            - 0.55 * exit_cap
            + 0.70 * run_params["market_rent_growth_min"]
            + 0.30 * run_params["initial_occupancy"]
            - run_params["purchase_price"] / 10_000_000_000
            - run_params["operating_expenses_start"] / 1_000_000_000
            + seed / 1_000_000
            + n / 10_000_000
        )
        return pd.DataFrame({"IRR": [value - 0.001, value, value + 0.001]})

    df = build_tornado_sensitivity_data(params, n_per_case=25, seed=7, runner=fake_runner)

    expected_columns = {
        "parameter",
        "low_case",
        "high_case",
        "base_metric",
        "low_metric",
        "high_metric",
        "low_delta",
        "high_delta",
        "status",
    }
    assert expected_columns.issubset(df.columns)
    assert len(calls) == 13
    assert set(df["status"]) == {"model-derived"}

    interest = df.set_index("parameter").loc["Interest Rate"]
    assert math.isclose(float(interest["low_delta"]), 0.009, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(float(interest["high_delta"]), -0.009, rel_tol=0, abs_tol=1e-12)

    fixed_demo_deltas = {-0.05, -0.03, -0.02, -0.01, 0.015, 0.02, 0.04}
    actual_deltas = {
        round(float(value), 6)
        for value in df[["low_delta", "high_delta"]].to_numpy().ravel()
    }
    assert not actual_deltas.issubset(fixed_demo_deltas)

