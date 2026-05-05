"""
Outliers & Data Health acceptance test.

11) Count pathological runs and ensure zero by default:
    - IRR > 100%, IRR < −100%
    - Negative NOI_Y1
    - CoC > 1000%
    - Any NaN/Inf in core metrics (IRR, NPV, CoC, EquityMultiple, DSCR)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import monte_carlo_model


SEED = 99
N = 2000


def test_outliers_and_data_health():
    df = monte_carlo_model.run_simulation(n=N, seed=SEED, params=monte_carlo_model.default_params(), parallel=True)

    irr = pd.to_numeric(df['IRR'], errors='coerce')
    npv = pd.to_numeric(df['NPV'], errors='coerce')
    coc = pd.to_numeric(df['CoC'], errors='coerce')
    em = pd.to_numeric(df['EquityMultiple'], errors='coerce')
    dscr = pd.to_numeric(df['DSCR'], errors='coerce') if 'DSCR' in df.columns else pd.to_numeric(df['DSCR_Y1'], errors='coerce')
    noi1 = pd.to_numeric(df['NOI_Y1'], errors='coerce') if 'NOI_Y1' in df.columns else pd.Series([], dtype=float)

    # Outlier counts
    out_irr_hi = int((irr > 1.0).sum())
    out_irr_lo = int((irr < -1.0).sum())
    out_noi_neg = int((noi1 < 0).sum()) if not noi1.empty else 0
    out_coc_hi = int((coc > 10.0).sum())

    # NaN/Inf in core metrics
    def _bad(s: pd.Series) -> int:
        return int((~np.isfinite(s)).sum())

    bad_counts = {
        'IRR': _bad(irr),
        'NPV': _bad(npv),
        'CoC': _bad(coc),
        'EquityMultiple': _bad(em),
        'DSCR': _bad(dscr),
    }

    assert out_irr_hi == 0, f"IRR > 100% outliers: {out_irr_hi}"
    assert out_irr_lo == 0, f"IRR < -100% outliers: {out_irr_lo}"
    assert out_noi_neg == 0, f"Negative NOI_Y1 outliers: {out_noi_neg}"
    assert out_coc_hi == 0, f"CoC > 1000% outliers: {out_coc_hi}"
    for k, v in bad_counts.items():
        assert v == 0, f"Non-finite values in {k}: {v}"

