"""Audit current DSCR, debt-yield, and NOI shock behavior.

This is an audit lock, not a model-fix test. It records the current annual
model contract so broad diagnostics can distinguish stale expectations from a
future approved financial-model change.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

import monte_carlo_model


SEED = 42
N = 200


MEAN_COLUMNS = (
    "IRR",
    "NPV",
    "CoC",
    "NOI_Y1",
    "DSCR",
    "DebtYield_Y1",
    "MinDebtYield",
    "OperatingExpenseRatio",
    "LTV",
)


def _run(params: dict) -> pd.DataFrame:
    return monte_carlo_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)


def _means(df: pd.DataFrame) -> dict[str, float]:
    missing = [column for column in MEAN_COLUMNS if column not in df.columns]
    assert not missing, f"Missing audit columns: {missing}"
    return {
        column: float(pd.to_numeric(df[column], errors="coerce").dropna().mean())
        for column in MEAN_COLUMNS
    }


def _same(actual: float, expected: float, abs_tol: float = 1e-9):
    assert actual == pytest.approx(expected, rel=0.0, abs=abs_tol)


def test_current_dscr_debt_yield_noi_shock_contract():
    """Record current same-seed behavior before any model-level repair."""
    base_params = monte_carlo_model.default_params()
    base_params["GLOBAL_RECOVERY_TYPE"] = "GROSS"
    base = _means(_run(base_params))

    shocks: dict[str, dict] = {}

    opex_up = copy.deepcopy(base_params)
    opex_up["operating_expenses_start"] *= 1.20
    shocks["opex_up"] = _means(_run(opex_up))

    opex_down = copy.deepcopy(base_params)
    opex_down["operating_expenses_start"] *= 0.80
    shocks["opex_down"] = _means(_run(opex_down))

    tax_up = copy.deepcopy(base_params)
    tax_up["property_tax_rate"] += 0.005
    shocks["tax_up"] = _means(_run(tax_up))

    rent_up = copy.deepcopy(base_params)
    rent_up["market_rent_psf"] *= 1.10
    rent_up["in_place_rent_psf"] *= 1.10
    shocks["rent_up"] = _means(_run(rent_up))

    debt_up = copy.deepcopy(base_params)
    debt_up["debt_ratio"] = min(0.75, debt_up["debt_ratio"] + 0.05)
    shocks["debt_up"] = _means(_run(debt_up))

    rate_up = copy.deepcopy(base_params)
    rate_up["interest_rate"] += 0.005
    shocks["rate_up"] = _means(_run(rate_up))

    # OpEx moves current return metrics and operating-expense ratio, but not
    # current Year 1 NOI/DSCR/DebtYield_Y1 outputs.
    assert shocks["opex_up"]["IRR"] < base["IRR"]
    assert shocks["opex_up"]["NPV"] < base["NPV"]
    assert shocks["opex_up"]["CoC"] < base["CoC"]
    assert shocks["opex_up"]["OperatingExpenseRatio"] > base["OperatingExpenseRatio"]
    _same(shocks["opex_up"]["NOI_Y1"], base["NOI_Y1"], abs_tol=1e-6)
    _same(shocks["opex_up"]["DSCR"], base["DSCR"])
    _same(shocks["opex_up"]["DebtYield_Y1"], base["DebtYield_Y1"])
    assert shocks["opex_up"]["MinDebtYield"] < base["MinDebtYield"]

    assert shocks["opex_down"]["IRR"] > base["IRR"]
    assert shocks["opex_down"]["NPV"] > base["NPV"]
    assert shocks["opex_down"]["CoC"] > base["CoC"]
    assert shocks["opex_down"]["OperatingExpenseRatio"] < base["OperatingExpenseRatio"]
    _same(shocks["opex_down"]["NOI_Y1"], base["NOI_Y1"], abs_tol=1e-6)
    _same(shocks["opex_down"]["DSCR"], base["DSCR"])
    _same(shocks["opex_down"]["DebtYield_Y1"], base["DebtYield_Y1"])
    assert shocks["opex_down"]["MinDebtYield"] > base["MinDebtYield"]

    # Tax moves IRR/NPV and MinDebtYield but leaves CoC and Year 1
    # NOI/DSCR/DebtYield_Y1 unchanged under the current annual contract.
    assert shocks["tax_up"]["IRR"] < base["IRR"]
    assert shocks["tax_up"]["NPV"] < base["NPV"]
    _same(shocks["tax_up"]["CoC"], base["CoC"])
    _same(shocks["tax_up"]["NOI_Y1"], base["NOI_Y1"], abs_tol=1e-6)
    _same(shocks["tax_up"]["DSCR"], base["DSCR"])
    _same(shocks["tax_up"]["DebtYield_Y1"], base["DebtYield_Y1"])
    assert shocks["tax_up"]["MinDebtYield"] < base["MinDebtYield"]

    # Non-expense shocks prove the risk metrics are not globally inert.
    assert shocks["rent_up"]["IRR"] > base["IRR"]
    assert shocks["rent_up"]["NPV"] > base["NPV"]
    assert shocks["rent_up"]["NOI_Y1"] > base["NOI_Y1"]
    assert shocks["rent_up"]["DSCR"] > base["DSCR"]
    assert shocks["rent_up"]["DebtYield_Y1"] > base["DebtYield_Y1"]

    assert shocks["debt_up"]["LTV"] > base["LTV"]
    assert shocks["debt_up"]["DSCR"] < base["DSCR"]
    assert shocks["debt_up"]["DebtYield_Y1"] < base["DebtYield_Y1"]

    assert shocks["rate_up"]["IRR"] < base["IRR"]
    assert shocks["rate_up"]["NPV"] < base["NPV"]
    assert shocks["rate_up"]["DSCR"] < base["DSCR"]
    _same(shocks["rate_up"]["NOI_Y1"], base["NOI_Y1"], abs_tol=1e-6)
    _same(shocks["rate_up"]["DebtYield_Y1"], base["DebtYield_Y1"])
