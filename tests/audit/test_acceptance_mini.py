"""
Mini Acceptance Pack — Base Case (deterministic)

Validates key numbers for a single seeded Base run against explicit
expected values with tolerances:
 - Equity need at t0: ±0.5%
 - Y1 DSCR: ±0.05x
 - IRR: ±50 bps (0.005 abs)
 - NPV: ±1.5%
 - Sale proceeds: ±1.0% (derived tv − costs − payoff − prepay)

Notes:
 - Exit cap override is OFF (triangular sampling as-is from defaults)
 - Seed pinned for reproducibility
 - No economic changes; this test only asserts outputs
"""

from __future__ import annotations

import math

import numpy as np

import monte_carlo_model


SEED = 12345

# Expected numbers recorded for Base defaults with SEED=12345
EXPECTED = {
    "equity": 66800984.65641257,
    "noi_y1": 14712019.212159991,
    "debtpay_y1": 3283665.2052356917,
    "dscr": 4.480365168989269,
    "irr": 0.18115673873068006,
    "npv": 37023929.10168564,
    "terminal_value": 161814520.10657126,
    "debt_payoff_exit": 75406670.06320386,
    "prepay_sale_cost": 0.0,
    # Derived sale proceeds ≈ tv − (sale_cost_rate+transfer_tax_sell_rate)*tv − payoff − prepay
    "sale_proceeds": 81553414.44017027,
}


def test_mini_acceptance_base_pack():
    params = monte_carlo_model.default_params()
    # Explain mode enables schedule exposure for recompute/validation
    res = monte_carlo_model.run_model({**params, "_seed": SEED, "explain_mode": True})

    # 1) Equity need at t0
    equity = float(res["Equity"])  # from engine
    rel_err_equity = abs(equity - EXPECTED["equity"]) / max(1.0, abs(EXPECTED["equity"]))
    assert rel_err_equity <= 0.005, (
        f"Equity t0 outside tolerance: got={equity:,.2f}, exp={EXPECTED['equity']:,.2f} (rel err {rel_err_equity:.3%})"
    )

    # 2) Year-1 DSCR from NOI_Y1 and Y1 debt service
    noi_y1 = float(res.get("NOI_Y1", float("nan")))
    debtpay_y1 = float(res.get("DebtPayment_Y1", float("nan")))
    dscr = noi_y1 / debtpay_y1 if (np.isfinite(noi_y1) and np.isfinite(debtpay_y1) and debtpay_y1 != 0) else float("nan")
    assert np.isfinite(dscr) and abs(dscr - EXPECTED["dscr"]) <= 0.05, (
        f"DSCR outside tolerance: got={dscr:.4f}, exp={EXPECTED['dscr']:.4f}"
    )

    # 3) IRR and NPV from equity cash-flow series (exact recompute)
    cfe = res.get("_ScheduleData", {}).get("cash_flows")
    assert isinstance(cfe, list) and cfe, "Missing schedule cash flows"
    cf_series = [-equity] + [float(x) for x in cfe]
    irr = monte_carlo_model.calculate_irr(cf_series)
    npv = monte_carlo_model.calculate_npv(float(params["discount_rate"]), cf_series)
    assert np.isfinite(irr) and abs(irr - EXPECTED["irr"]) <= 0.005, (
        f"IRR outside ±50 bps: got={irr:.6f}, exp={EXPECTED['irr']:.6f}"
    )
    rel_err_npv = abs(npv - EXPECTED["npv"]) / max(1.0, abs(EXPECTED["npv"]))
    assert np.isfinite(npv) and rel_err_npv <= 0.015, (
        f"NPV outside ±1.5%: got={npv:,.2f}, exp={EXPECTED['npv']:,.2f} (rel err {rel_err_npv:.3%})"
    )

    # 4) Sale proceeds from terminal inputs (approximation per policy)
    tv = float(res.get("TerminalValue", float("nan")))
    payoff = float(res.get("Debt_EndBal_Exit", 0.0))
    prepay = float(res.get("Prepay_Cost_Sale", 0.0) or 0.0)
    sale_cost_rate = float(params.get("sale_cost_rate", 0.0)) + float(params.get("transfer_tax_sell_rate", 0.0))
    sale_proceeds = tv - sale_cost_rate * tv - payoff - prepay
    rel_err_sale = abs(sale_proceeds - EXPECTED["sale_proceeds"]) / max(1.0, abs(EXPECTED["sale_proceeds"]))
    assert np.isfinite(sale_proceeds) and rel_err_sale <= 0.01, (
        f"Sale proceeds outside ±1%: got={sale_proceeds:,.2f}, exp={EXPECTED['sale_proceeds']:,.2f} (rel err {rel_err_sale:.3%})"
    )

