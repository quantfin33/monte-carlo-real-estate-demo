"""
Deterministic Acceptance (Base Case)

Recompute key acceptance numbers for a single seeded run and compare
to model outputs within tolerances.

Tolerances:
- IRR: ±50 bps (0.005 absolute)
- NPV: ±1.5% (relative to model NPV, with floor)
- DSCR: ±0.05x
- Equity @ t0: ±0.5% (relative to model Equity)

Note: For IRR/NPV, we approximate equity cash flows using only CF0 and
final sale proceeds (no intermediate distributions). This should be
close for a stabilized hold and is sufficient for acceptance.
"""

from __future__ import annotations

import math

import numpy as np

import rmc_model


SEED = 12345


def _approx_sale_proceeds(res: dict, params: dict) -> float:
    tv = float(res["TerminalValue"])  # terminal value
    sale_costs = tv * float(params.get("sale_cost_rate", 0.0)) + tv * float(params.get("transfer_tax_sell_rate", 0.0))
    payoff = float(res.get("Debt_EndBal_Exit", 0.0))
    prepay = float(res.get("Prepay_Cost_Sale", 0.0) or 0.0)
    return tv - sale_costs - payoff - prepay


def _recompute_equity(res: dict, params: dict) -> float:
    # Recover total_cost via loan_amount / debt_ratio
    loan_amount = float(res["Debt_BegBal_Y1"])  # day-0 loan
    debt_ratio = float(params["debt_ratio"]) if params.get("debt_ratio") is not None else 0.0
    total_cost = loan_amount / debt_ratio if debt_ratio > 0 else float("nan")

    purchase_price = float(params["purchase_price"])  # acq costs apply to purchase price
    acq_costs = purchase_price * float(params.get("acq_cost_rate", 0.0))
    financing_fees = loan_amount * float(params.get("financing_fee_rate", 0.0))
    rc_param = float(params.get("rate_cap_cost", 0.0))
    rate_cap_cost = loan_amount * rc_param if rc_param < 1 else rc_param
    contingency = float(params.get("contingency_reserve", 0.0))
    wc_reserve = float(params.get("working_capital_reserve", 0.0))
    seller_credit = float(params.get("seller_reserve_credit", 0.0))
    transfer_tax_buy = purchase_price * float(params.get("transfer_tax_buy_rate", 0.0))
    wc_true_up_close = float(params.get("wc_true_up_close_dollar", 0.0)) + float(params.get("wc_true_up_close_pct_of_opex", 0.0)) * float(params.get("operating_expenses_start", 0.0))

    equity = (
        total_cost
        + acq_costs
        + financing_fees
        + rate_cap_cost
        + contingency
        + wc_reserve
        + transfer_tax_buy
        + wc_true_up_close
        - seller_credit
        - loan_amount
    )
    return float(equity)


def test_acceptance_base_numbers():
    params = rmc_model.default_params()
    # Enable explain_mode to expose _CashFlowSeries for exact IRR/NPV recompute
    res = rmc_model.run_model({**params, "_seed": SEED, "explain_mode": True})

    # 1) Equity @ t0
    equity_model = float(res["Equity"])
    equity_re = _recompute_equity(res, params)
    rel_err_equity = abs(equity_re - equity_model) / max(1.0, abs(equity_model))
    assert rel_err_equity <= 0.005, f"Equity t0 mismatch: model={equity_model:,.2f}, recompute={equity_re:,.2f} (rel err {rel_err_equity:.3%})"

    # 2) Year 1 NOI (per NNN rules) — use model output; ensure finite
    noi_y1 = float(res["NOI_Y1"]) if res.get("NOI_Y1") is not None else float("nan")
    assert np.isfinite(noi_y1), "NOI_Y1 should be finite"

    # 3) Year 1 DSCR
    dscr_model = float(res["DSCR"]) if res.get("DSCR") is not None else float("nan")
    debtpay_y1 = float(res.get("DebtPayment_Y1", float("nan")))
    dscr_re = noi_y1 / debtpay_y1 if (np.isfinite(noi_y1) and np.isfinite(debtpay_y1) and debtpay_y1 != 0) else float("nan")
    assert np.isfinite(dscr_re) and abs(dscr_re - dscr_model) <= 0.05, (
        f"DSCR mismatch: model={dscr_model:.3f}, recompute={dscr_re:.3f}"
    )

    # 4) Sale proceeds (approximation)
    sale_proceeds_approx = _approx_sale_proceeds(res, params)
    assert np.isfinite(sale_proceeds_approx) and sale_proceeds_approx > 0

    # 5) IRR & NPV — recompute exactly from engine cash flows (exposed via explain_mode)
    sched = res.get("_ScheduleData", {})
    cfe = sched.get("cash_flows")
    assert isinstance(cfe, list) and len(cfe) >= 1, "_ScheduleData.cash_flows not available"
    cf_series = [-equity_model] + [float(x) for x in cfe]
    irr_approx = rmc_model.calculate_irr(cf_series)
    npv_approx = rmc_model.calculate_npv(float(params["discount_rate"]), cf_series)

    irr_model = float(res["IRR"]) if res.get("IRR") is not None else float("nan")
    npv_model = float(res["NPV"]) if res.get("NPV") is not None else float("nan")

    # Tolerances
    assert np.isfinite(irr_approx) and abs(irr_approx - irr_model) <= 0.005, (
        f"IRR mismatch: model={irr_model:.4f}, approx={irr_approx:.4f}"
    )
    rel_err_npv = abs(npv_approx - npv_model) / max(1.0, abs(npv_model))
    assert np.isfinite(npv_approx) and rel_err_npv <= 0.015, (
        f"NPV mismatch: model={npv_model:,.2f}, approx={npv_approx:,.2f} (rel err {rel_err_npv:.3%})"
    )
