"""Financial Metric Sensitivity Contract v1.

This file locks the recovery-sensitive metric contract without changing the
financial formulas. Recovery type controls whether OpEx/tax shocks are recovered
from tenants or flow through Year 1 NOI, DSCR, and debt yield.
"""

from __future__ import annotations

import copy
import math

import pandas as pd
import pytest

import monte_carlo_model


SEED = 42
N = 24


MEAN_COLUMNS = (
    "NOI_Y1",
    "DSCR",
    "DSCR_Y1",
    "DebtYield_Y1",
    "MinDebtYield",
    "CoC",
    "NPV",
    "IRR",
    "EquityMultiple",
    "DebtPayment_Y1",
    "Debt_BegBal_Y1",
    "BreakEvenOcc",
    "PropertyTaxSeries",
)


def _params(recovery_type: str) -> dict:
    params = monte_carlo_model.default_params()
    params["GLOBAL_RECOVERY_TYPE"] = recovery_type
    return params


def _run(params: dict) -> pd.DataFrame:
    return monte_carlo_model.run_simulation(n=N, seed=SEED, params=params, parallel=False)


def _mean_field(df: pd.DataFrame, column: str) -> float:
    if column == "PropertyTaxSeries":
        values = [row[0] if isinstance(row, list) and row else math.nan for row in df[column]]
        return float(pd.Series(values).dropna().mean())
    return float(pd.to_numeric(df[column], errors="coerce").dropna().mean())


def _means(params: dict) -> dict[str, float]:
    df = _run(params)
    missing = [column for column in MEAN_COLUMNS if column not in df.columns]
    assert not missing, f"Missing contract columns: {missing}"
    return {column: _mean_field(df, column) for column in MEAN_COLUMNS}


def _shock(params: dict, **overrides) -> dict:
    shocked = copy.deepcopy(params)
    for key, value in overrides.items():
        shocked[key] = value(shocked[key]) if callable(value) else value
    return shocked


def test_params_recovery_type_controls_reconstructed_lease_roll():
    params = monte_carlo_model.run_model(
        {"GLOBAL_RECOVERY_TYPE": "BASE_YEAR"},
        return_params_only=True,
    )
    assert {tenant["recovery_type"] for tenant in params["lease_roll"]} == {"BASE_YEAR"}

    params = monte_carlo_model.run_model(
        {"GLOBAL_RECOVERY_TYPE": "GROSS"},
        return_params_only=True,
    )
    assert {tenant["recovery_type"] for tenant in params["lease_roll"]} == {"GROSS"}


def test_dscr_and_debt_yield_recompute_from_year_one_components():
    df = _run(_params("GROSS"))

    for row in df.to_dict("records"):
        assert row["DSCR_Y1"] == pytest.approx(
            row["NOI_Y1"] / row["DebtPayment_Y1"],
            rel=1e-12,
        )
        assert row["DebtYield_Y1"] == pytest.approx(
            row["NOI_Y1"] / row["Debt_BegBal_Y1"],
            rel=1e-12,
        )


def test_nnn_recovers_opex_and_tax_but_breakeven_tracks_cost_pressure():
    base = _means(_params("NNN"))
    opex_up = _means(
        _shock(_params("NNN"), operating_expenses_start=lambda value: value * 1.20)
    )
    tax_up = _means(_shock(_params("NNN"), property_tax_rate=lambda value: value + 0.005))

    assert opex_up["BreakEvenOcc"] > base["BreakEvenOcc"]
    assert tax_up["BreakEvenOcc"] > base["BreakEvenOcc"]
    assert tax_up["PropertyTaxSeries"] > base["PropertyTaxSeries"]

    assert opex_up["NOI_Y1"] == pytest.approx(base["NOI_Y1"])
    assert opex_up["DSCR"] == pytest.approx(base["DSCR"])
    assert opex_up["DebtYield_Y1"] == pytest.approx(base["DebtYield_Y1"])
    assert tax_up["NOI_Y1"] == pytest.approx(base["NOI_Y1"])
    assert tax_up["DSCR"] == pytest.approx(base["DSCR"])
    assert tax_up["DebtYield_Y1"] == pytest.approx(base["DebtYield_Y1"])


@pytest.mark.parametrize("recovery_type", ["GROSS", "BASE_YEAR", "CAM_CAP"])
def test_unrecovered_or_partially_recovered_opex_worsens_year_one_risk_metrics(recovery_type):
    base = _means(_params(recovery_type))
    opex_up = _means(
        _shock(_params(recovery_type), operating_expenses_start=lambda value: value * 1.20)
    )

    assert opex_up["NOI_Y1"] < base["NOI_Y1"]
    assert opex_up["DSCR"] < base["DSCR"]
    assert opex_up["DSCR_Y1"] < base["DSCR_Y1"]
    assert opex_up["DebtYield_Y1"] < base["DebtYield_Y1"]
    assert opex_up["CoC"] < base["CoC"]
    assert opex_up["NPV"] < base["NPV"]
    assert opex_up["IRR"] < base["IRR"]
    assert opex_up["EquityMultiple"] < base["EquityMultiple"]


@pytest.mark.parametrize("recovery_type", ["GROSS", "BASE_YEAR", "CAM_CAP"])
def test_unrecovered_or_partially_recovered_tax_worsens_year_one_risk_metrics(recovery_type):
    base = _means(_params(recovery_type))
    tax_up = _means(_shock(_params(recovery_type), property_tax_rate=lambda value: value + 0.005))

    assert tax_up["PropertyTaxSeries"] > base["PropertyTaxSeries"]
    assert tax_up["NOI_Y1"] < base["NOI_Y1"]
    assert tax_up["DSCR"] < base["DSCR"]
    assert tax_up["DSCR_Y1"] < base["DSCR_Y1"]
    assert tax_up["DebtYield_Y1"] < base["DebtYield_Y1"]
    assert tax_up["CoC"] < base["CoC"]
    assert tax_up["NPV"] < base["NPV"]
    assert tax_up["IRR"] < base["IRR"]
    assert tax_up["EquityMultiple"] < base["EquityMultiple"]


def test_interest_rate_shock_lowers_dscr_but_not_debt_yield():
    base = _means(_params("GROSS"))
    rate_up = _means(_shock(_params("GROSS"), interest_rate=lambda value: value + 0.005))

    assert rate_up["DebtPayment_Y1"] > base["DebtPayment_Y1"]
    assert rate_up["DSCR"] < base["DSCR"]
    assert rate_up["CoC"] < base["CoC"]
    assert rate_up["NPV"] < base["NPV"]
    assert rate_up["IRR"] < base["IRR"]
    assert rate_up["DebtYield_Y1"] == pytest.approx(base["DebtYield_Y1"])


def test_debt_ratio_shock_lowers_dscr_and_debt_yield_without_moving_noi():
    base = _means(_params("GROSS"))
    debt_up = _means(_shock(_params("GROSS"), debt_ratio=lambda value: value + 0.05))

    assert debt_up["DebtPayment_Y1"] > base["DebtPayment_Y1"]
    assert debt_up["NOI_Y1"] == pytest.approx(base["NOI_Y1"])
    assert debt_up["DSCR"] < base["DSCR"]
    assert debt_up["DebtYield_Y1"] < base["DebtYield_Y1"]


def test_exit_cap_shock_moves_value_metrics_not_year_one_operating_metrics():
    base = _means(_params("GROSS"))
    exit_cap_up = _means(_shock(_params("GROSS"), exit_cap_override=0.095))

    assert exit_cap_up["NOI_Y1"] == pytest.approx(base["NOI_Y1"])
    assert exit_cap_up["DSCR"] == pytest.approx(base["DSCR"])
    assert exit_cap_up["DebtYield_Y1"] == pytest.approx(base["DebtYield_Y1"])
    assert exit_cap_up["NPV"] < base["NPV"]
    assert exit_cap_up["IRR"] < base["IRR"]
    assert exit_cap_up["EquityMultiple"] < base["EquityMultiple"]
