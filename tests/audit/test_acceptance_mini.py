"""
Mini Acceptance Pack — Base Case (deterministic)

Validates key numbers for a single seeded Base run against internal
current-model recomputations:
 - Equity need at t0 is finite and positive
 - Y1 DSCR recomputes from NOI_Y1 / debt service
 - IRR and NPV recompute from exposed equity cash-flow series
 - Sale proceeds recompute from terminal value, sale costs, payoff, and prepay

Notes:
 - Exit cap override is OFF (triangular sampling as-is from defaults)
 - Seed pinned for reproducibility
 - No economic changes; this test only asserts current-model consistency
"""

from __future__ import annotations

import numpy as np

import monte_carlo_model


SEED = 12345


def test_mini_acceptance_base_pack():
    params = monte_carlo_model.default_params()
    # Explain mode enables schedule exposure for recompute/validation
    res = monte_carlo_model.run_model({**params, "_seed": SEED, "explain_mode": True})

    # 1) Equity need at t0
    equity = float(res["Equity"])  # from engine
    assert np.isfinite(equity) and equity > 0, f"Equity t0 should be finite and positive: got={equity:,.2f}"

    # 2) Year-1 DSCR from NOI_Y1 and Y1 debt service
    noi_y1 = float(res.get("NOI_Y1", float("nan")))
    debtpay_y1 = float(res.get("DebtPayment_Y1", float("nan")))
    dscr = noi_y1 / debtpay_y1 if (np.isfinite(noi_y1) and np.isfinite(debtpay_y1) and debtpay_y1 != 0) else float("nan")
    model_dscr = float(res.get("DSCR", float("nan")))
    assert np.isfinite(dscr) and abs(dscr - model_dscr) <= 0.05, (
        f"DSCR recompute mismatch: got={dscr:.4f}, model={model_dscr:.4f}"
    )

    # 3) IRR and NPV from equity cash-flow series (exact recompute)
    cfe = res.get("_ScheduleData", {}).get("cash_flows")
    assert isinstance(cfe, list) and cfe, "Missing schedule cash flows"
    cf_series = [-equity] + [float(x) for x in cfe]
    irr = monte_carlo_model.calculate_irr(cf_series)
    npv = monte_carlo_model.calculate_npv(float(params["discount_rate"]), cf_series)
    model_irr = float(res.get("IRR", float("nan")))
    model_npv = float(res.get("NPV", float("nan")))
    assert np.isfinite(irr) and abs(irr - model_irr) <= 0.005, (
        f"IRR recompute mismatch: got={irr:.6f}, model={model_irr:.6f}"
    )
    rel_err_npv = abs(npv - model_npv) / max(1.0, abs(model_npv))
    assert np.isfinite(npv) and rel_err_npv <= 0.015, (
        f"NPV recompute mismatch: got={npv:,.2f}, model={model_npv:,.2f} (rel err {rel_err_npv:.3%})"
    )

    # 4) Sale proceeds from terminal inputs (current model policy)
    tv = float(res.get("TerminalValue", float("nan")))
    payoff = float(res.get("Debt_EndBal_Exit", 0.0))
    prepay = float(res.get("Prepay_Cost_Sale", 0.0) or 0.0)
    sale_cost_rate = float(params.get("sale_cost_rate", 0.0)) + float(params.get("transfer_tax_sell_rate", 0.0))
    sale_proceeds = tv - sale_cost_rate * tv - payoff - prepay
    terminal_data = res.get("_ScheduleData", {}).get("terminal", {}) or res.get("_TerminalData", {})
    terminal_net_sale = terminal_data.get("net_sale_proceeds") if isinstance(terminal_data, dict) else None
    assert np.isfinite(sale_proceeds) and sale_proceeds > 0
    if terminal_net_sale is not None:
        rel_err_sale = abs(sale_proceeds - float(terminal_net_sale)) / max(1.0, abs(float(terminal_net_sale)))
        assert rel_err_sale <= 0.01, (
            f"Sale proceeds recompute mismatch: got={sale_proceeds:,.2f}, "
            f"terminal={float(terminal_net_sale):,.2f} (rel err {rel_err_sale:.3%})"
        )
