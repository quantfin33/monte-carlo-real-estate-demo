from __future__ import annotations

import math

import pandas as pd

import monte_carlo_model


def _p50(df: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    assert not values.empty, f"{column} has no finite values"
    result = float(values.quantile(0.50))
    assert math.isfinite(result), f"{column} p50 is not finite"
    return result


def test_default_demo_returns_are_reasonable_for_portfolio_review() -> None:
    """The default scenario is a demo baseline, not market validation."""
    params = monte_carlo_model.default_params()
    df = monte_carlo_model.run_simulation(n=500, seed=123, params=params, parallel=False)

    irr_p50 = _p50(df, "IRR")
    npv_p50 = _p50(df, "NPV")
    coc_p50 = _p50(df, "CoC")
    dscr_p50 = _p50(df, "DSCR")
    ltv_p50 = _p50(df, "LTV")

    assert 0.06 <= irr_p50 <= 0.14
    assert -15_000_000 <= npv_p50 <= 20_000_000
    assert 0.04 <= coc_p50 <= 0.16
    assert 1.25 <= dscr_p50 <= 4.00
    assert 0.30 <= ltv_p50 <= 0.70
