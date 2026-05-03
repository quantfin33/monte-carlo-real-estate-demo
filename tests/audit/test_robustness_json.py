"""
Robustness & Edge Cases

12) Metrics layer handles empty/missing/wrong types safely
13) JSON serialization of engine/metrics payloads via a safe encoder
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd

import rmc_model
import ui_metrics
from safe_json import SafeJSONEncoder, dumps as json_dumps


def test_metrics_handle_empty_and_missing():
    # Empty DataFrame
    empty = pd.DataFrame()

    # All functions should return dicts and not raise
    irr = ui_metrics.irr_stats(empty)
    rv = ui_metrics.return_value_metrics(empty)
    ro = ui_metrics.risk_ops_metrics(empty)

    assert isinstance(irr, dict) and 'mean' in irr
    assert isinstance(rv, dict) and 'coc' in rv and 'npv' in rv
    assert isinstance(ro, dict) and 'dscr' in ro

    # Missing columns and wrong types
    df_bad = pd.DataFrame({
        'IRR': ['not', 'numbers'],
        'CoC': ['bad', None],
        'NPV': [object(), object()],
    })
    irr2 = ui_metrics.irr_stats(df_bad)
    rv2 = ui_metrics.return_value_metrics(df_bad)
    assert isinstance(irr2, dict) and 'mean' in irr2
    assert isinstance(rv2, dict) and 'coc' in rv2 and 'npv' in rv2


def test_safe_json_encoder_serializes_engine_and_metrics():
    params = rmc_model.default_params()
    # Engine result with explain payload
    res = rmc_model.run_model({**params, '_seed': 123, 'explain_mode': True})

    # Should serialize using safe encoder
    s1 = json.dumps(res, cls=SafeJSONEncoder)
    assert isinstance(s1, str) and len(s1) > 0

    # Simulation DF to JSON-esque dict
    df = rmc_model.run_simulation(n=100, seed=77, params=params, parallel=True)
    df_dict = df.to_dict(orient='list')
    s2 = json_dumps(df_dict)
    assert isinstance(s2, str) and len(s2) > 0

    # Metrics payload serialization
    metrics_payload = {
        'irr': ui_metrics.irr_stats(df),
        'returns': ui_metrics.return_value_metrics(df),
        'risk': ui_metrics.risk_ops_metrics(df),
    }
    s3 = json_dumps(metrics_payload)
    assert isinstance(s3, str) and len(s3) > 0

