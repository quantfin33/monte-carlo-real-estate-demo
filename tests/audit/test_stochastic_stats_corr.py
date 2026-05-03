"""
Stochastic Stats & Correlations (Acceptance)

7) Report mean/p05/p50/p95 for IRR, NPV, CoC, EquityMultiple, DSCR and flag
   implausibly tight/wide bands (warnings, not failures).
8) Ensure per-run ExitCap is present and corr(IRR, ExitCap) is materially negative.
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

import rmc_model


SEED = 44
N = 1200


def _pctiles(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return float("nan"), float("nan"), float("nan"), float("nan")
    return float(s.mean()), float(np.percentile(s, 5)), float(np.percentile(s, 50)), float(np.percentile(s, 95))


def test_stochastic_stats_and_exitcap_corr():
    df = rmc_model.run_simulation(n=N, seed=SEED, params=rmc_model.default_params(), parallel=True)

    # 7) Distributions report
    metrics = {
        'IRR': df.get('IRR'),
        'NPV': df.get('NPV'),
        'CoC': df.get('CoC'),
        'EquityMultiple': df.get('EquityMultiple'),
        'DSCR': df.get('DSCR') if 'DSCR' in df.columns else df.get('DSCR_Y1'),
    }

    for name, series in metrics.items():
        assert series is not None, f"Missing metric column: {name}"
        mean, p05, p50, p95 = _pctiles(series)
        # Basic sanity
        assert not any(np.isnan(x) for x in (mean, p05, p50, p95)), f"NaN stats for {name}"
        assert p05 <= p50 <= p95, f"Percentiles out of order for {name}"

        # Flag implausibly tight/wide bands (warn only)
        band = p95 - p05
        if name == 'IRR' and band < 0.003:
            warnings.warn(f"IRR band too tight (p95-p05={band:.4f})", RuntimeWarning)
        if name == 'DSCR' and band < 0.01:
            warnings.warn(f"DSCR band too tight (p95-p05={band:.4f})", RuntimeWarning)
        if name == 'NPV' and band < 1e5:
            warnings.warn(f"NPV band too tight (p95-p05={band:,.0f})", RuntimeWarning)

    # 8) Exit-cap correlation with IRR
    # Ensure ExitCap present; if not, this test will naturally fail with KeyError.
    assert 'ExitCap' in df.columns, "ExitCap column missing; export it from the engine"
    irr = pd.to_numeric(df['IRR'], errors='coerce')
    xc = pd.to_numeric(df['ExitCap'], errors='coerce')
    aligned = pd.concat([irr, xc], axis=1).dropna()
    assert len(aligned) > 10, "Not enough data for correlation"
    corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
    # Materially negative indicates higher exit cap (worse pricing) reduces IRR
    assert corr < -0.10, f"IRR vs ExitCap correlation should be negative; got {corr:.3f}"

