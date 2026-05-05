from __future__ import annotations

import math

import numpy as np

import monte_carlo_model
import trace_tools


SEED = 314
N = 320


def _selected_run_row(df, run_idx: int):
    if '_RunIndex' in df.columns:
        matches = df.loc[df['_RunIndex'] == run_idx]
        if not matches.empty:
            return matches.iloc[0]
    return df.iloc[int(run_idx)]


def test_trace_payload_recomputes_metrics_and_reconciles_terminal_bridge():
    params = monte_carlo_model.default_params()
    df = monte_carlo_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)

    run_idx, _ = trace_tools.find_median_run(df)
    selected = _selected_run_row(df, run_idx)
    selected_irr = float(selected['IRR'])

    bundle = trace_tools.run_trace_simulation(
        params=params,
        base_seed=SEED,
        run_idx=run_idx,
        mode="p50_trace",
        expected_irr=selected_irr,
    )

    assert 'error' not in bundle, bundle.get('error')

    derived_seed = trace_tools._derive_seed_for_run(SEED, run_idx)
    res = monte_carlo_model.run_model({**params, '_seed': derived_seed, '_RunIndex': run_idx, 'explain_mode': True})

    assert res.get('_ExplainMode') is True
    assert res.get('_ExplainIdentity', {}).get('derived_seed') == derived_seed
    assert res.get('_ExplainIdentity', {}).get('run_index') == run_idx

    equity_cf = [float(x) for x in res['equity_cf']]
    assert equity_cf == bundle['trace_cashflows']['cash_flow_series']
    assert res['_CashFlowSeries'] == res['equity_cf']
    assert res['_ScheduleData']['cash_flows'] == equity_cf[1:]

    irr_re = monte_carlo_model.calculate_irr(equity_cf)
    npv_re = monte_carlo_model.calculate_npv(float(params['discount_rate']), equity_cf)

    assert np.isfinite(irr_re)
    assert math.isclose(irr_re, float(res['IRR']), abs_tol=1e-8)
    assert math.isclose(npv_re, float(res['NPV']), rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(float(res['IRR']), selected_irr, abs_tol=1e-8)

    term = res['_TerminalData']
    for key in (
        'noi_basis',
        'exit_cap_rate',
        'gross_sale_price',
        'sale_costs',
        'net_sale_before_debt_and_tax',
        'sale_tax',
        'debt_payoff',
        'prepay_cost',
        'wc_reserve_return',
        'wc_true_up_sale',
        'reserve_return',
        'contingency_return',
        'net_sale_proceeds',
    ):
        assert key in term, f"Missing trace terminal field: {key}"
        assert term[key] is not None, f"Trace terminal field should not be None: {key}"

    reconciled = (
        float(term['net_sale_before_debt_and_tax'])
        - float(term['sale_tax'])
        - float(term['debt_payoff'])
        - float(term['prepay_cost'])
        + float(term['wc_reserve_return'])
        + float(term['wc_true_up_sale'])
        + float(term['reserve_return'])
        + float(term['contingency_return'])
    )
    assert math.isclose(reconciled, float(term['net_sale_proceeds']), rel_tol=1e-9, abs_tol=1e-6)

