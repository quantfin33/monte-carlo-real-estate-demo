from __future__ import annotations

import math

import numpy as np

import monte_carlo_model


SEED = 42


def _base_refi_params() -> dict:
    params = monte_carlo_model.default_params()
    params.update(
        {
            "_seed": SEED,
            "explain_mode": True,
            "debug_return_schedule": True,
            "refi_year": 5,
            "refi_cost_rate": 0.0,
            "refi_boxes": {"enabled": False, "lockout_years": 0, "max_ltv": 0.75, "min_dscr": 1.25, "min_dy": 0.08},
            "prepay": {**dict(params.get("prepay", {})), "model": "none"},
            "prepay_at_sale": False,
            "sale_month": None,
        }
    )
    return params


def _assert_one_annual_cash_flow_bucket(result: dict) -> None:
    schedule = result["_ScheduleData"]
    years = schedule["years"]
    cash_flows = schedule["cash_flows"]

    assert years == list(range(1, max(years) + 1))
    assert len(cash_flows) == len(years)
    assert len(result["equity_cf"]) == len(years) + 1
    assert result["_CashFlowSeries"] == result["equity_cf"]
    assert result["_ScheduleData"]["cash_flows"] == result["equity_cf"][1:]

    irr_recomputed = monte_carlo_model.calculate_irr(result["equity_cf"])
    npv_recomputed = monte_carlo_model.calculate_npv(float(_base_refi_params()["discount_rate"]), result["equity_cf"])
    assert np.isfinite(irr_recomputed)
    assert math.isclose(irr_recomputed, float(result["IRR"]), abs_tol=1e-10)
    assert math.isclose(npv_recomputed, float(result["NPV"]), rel_tol=1e-10, abs_tol=1e-5)


def test_refi_cash_out_is_combined_with_same_year_annual_cash_flow() -> None:
    refi_params = _base_refi_params()
    refi_result = monte_carlo_model.run_model(refi_params)

    assert refi_result["Refi_Executed"] is True
    _assert_one_annual_cash_flow_bucket(refi_result)

    schedule = refi_result["_ScheduleData"]
    refi_indices = [i for i, event_type in enumerate(schedule["event_types"]) if "refi" in event_type]
    assert refi_indices == [4]
    refi_idx = refi_indices[0]
    assert schedule["years"][refi_idx] == 5

    refi_cash_out = schedule["refi_cash_out"][refi_idx]
    assert refi_cash_out > 0
    assert all(value == 0.0 for i, value in enumerate(schedule["refi_cash_out"]) if i != refi_idx)

    no_refi_params = {**refi_params, "refi_year": 0}
    no_refi_result = monte_carlo_model.run_model(no_refi_params)
    assert no_refi_result["Refi_Executed"] is False
    _assert_one_annual_cash_flow_bucket(no_refi_result)

    same_year_operating_cash_flow = no_refi_result["_ScheduleData"]["cash_flows"][refi_idx]
    expected_combined_cash_flow = same_year_operating_cash_flow + refi_cash_out
    actual_combined_cash_flow = schedule["cash_flows"][refi_idx]

    assert math.isclose(actual_combined_cash_flow, expected_combined_cash_flow, rel_tol=1e-10, abs_tol=1e-5)


def test_no_refi_case_has_no_duplicate_cash_flow_periods() -> None:
    params = _base_refi_params()
    params["refi_year"] = 0

    result = monte_carlo_model.run_model(params)

    assert result["Refi_Executed"] is False
    _assert_one_annual_cash_flow_bucket(result)
    assert "operations+refi" not in result["_ScheduleData"]["event_types"]
    assert all(value == 0.0 for value in result["_ScheduleData"]["refi_cash_out"])
