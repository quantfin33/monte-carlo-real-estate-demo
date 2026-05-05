"""
Explain P50 acceptance test.

9) Trace payload completeness: equity_cf and terminal fields
10) IRR recompute from equity_cf matches model IRR within 10 bps
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

import monte_carlo_model


SEED = 77
N = 800


def _run_index_for_seed(base_seed: int, i: int) -> int:
    # Mirror run_simulation seed scheme: seeds[i] = base + i*10007 + 7919
    return base_seed + i * 10007 + 7919


def test_explain_p50_trace_and_irr_recompute():
    params = monte_carlo_model.default_params()
    # Get a batch of runs to locate an approximate median IRR run index
    df = monte_carlo_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)
    irr = pd.to_numeric(df['IRR'], errors='coerce')
    median_val = float(np.nanmedian(irr))
    # Pick the run with IRR closest to median
    idx = int((irr - median_val).abs().idxmin())

    # Derive that run's seed and re-run with explain_mode for full payload
    this_seed = _run_index_for_seed(SEED, idx)
    res = monte_carlo_model.run_model({**params, '_seed': this_seed, 'explain_mode': True})

    # 9) Trace payload completeness
    assert isinstance(res.get('equity_cf'), list) and len(res['equity_cf']) >= 2, 'equity_cf missing'
    term = res.get('_TerminalData')
    assert isinstance(term, dict), 'TerminalData missing'
    for k in ['noi_basis', 'exit_cap_rate', 'gross_sale_price', 'sale_costs', 'debt_payoff', 'prepay_cost', 'net_sale_proceeds']:
        assert k in term, f'Missing terminal field: {k}'

    # 10) IRR recompute ≈ model IRR
    cf = [float(x) for x in res['equity_cf']]
    irr_re = monte_carlo_model.calculate_irr(cf)
    irr_model = float(res['IRR'])
    diff = abs(irr_re - irr_model)
    assert np.isfinite(irr_re), 'Recomputed IRR is NaN/Inf'
    assert diff <= 0.001, f'IRR mismatch > 10 bps: model={irr_model:.6f}, recompute={irr_re:.6f}, diff={diff:.6f}'

