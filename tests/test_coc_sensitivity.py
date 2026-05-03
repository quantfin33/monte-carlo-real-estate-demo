"""
CoC Sensitivity Tests - Real assertions without print statements.

Tests that Cash-on-Cash return and DSCR respond correctly to OpEx and Tax changes.
Uses actual model runs with deterministic seeds for reliable testing.
"""

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import rmc_model
import pandas as pd
import numpy as np
import pytest


def run_df(n=800, seed=123, overrides: dict | None = None) -> pd.DataFrame:
    """Run the model deterministically with optional parameter overrides."""
    params = rmc_model.default_params().copy()
    # Ensure we use GROSS lease for OpEx sensitivity
    params['GLOBAL_RECOVERY_TYPE'] = 'GROSS'
    if overrides:
        for k, v in overrides.items():
            params[k] = v
    params["_seed"] = int(seed)
    df = rmc_model.run_simulation(n=int(n), seed=int(seed), params=params, parallel=False)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)


def get_coc_series(df: pd.DataFrame) -> pd.Series:
    """Extract CoC series with graceful fallback if column name differs."""
    for name in ["CoC", "CashOnCash", "cash_on_cash"]:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").dropna()
    # last-resort fallback: Year1 cash flow / Equity if both present
    if {"Year1_CashFlow", "Equity"} <= set(df.columns):
        y1 = pd.to_numeric(df["Year1_CashFlow"], errors="coerce")
        eq = pd.to_numeric(df["Equity"], errors="coerce").replace(0, np.nan)
        return (y1 / eq).dropna()
    raise AssertionError("CoC column not found and fallback not possible")


def get_dscr_series(df: pd.DataFrame) -> pd.Series:
    """Extract DSCR series with fallback to alternative column names."""
    for name in ["MinDSCR", "Min_DSCR", "DSCR_Min", "DSCR"]:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").dropna()
    raise AssertionError("DSCR column not found")


def test_coc_decreases_when_opex_increases():
    """Test that CoC decreases when OpEx increases by 30%."""
    base_df = run_df(seed=42)
    base_params = rmc_model.default_params()
    opex0 = float(base_params.get("operating_expenses_start", 0))
    shocked_df = run_df(seed=43, overrides={"operating_expenses_start": opex0 * 1.30})

    b = get_coc_series(base_df)
    s = get_coc_series(shocked_df)
    
    # Check that we have valid data
    assert len(b) > 0 and len(s) > 0, "CoC series must not be empty"
    
    # Use a tolerance for floating point comparison
    mean_diff = b.mean() - s.mean()
    median_diff = b.median() - s.median()
    
    assert mean_diff > 0.001, f"CoC mean should drop significantly when OpEx +30% (diff={mean_diff:.6f})"
    assert median_diff > 0.0005, f"CoC median should drop when OpEx +30% (diff={median_diff:.6f})"


@pytest.mark.parametrize("bump", [0.25, 0.40])
def test_dscr_drops_with_opex(bump):
    """Test that DSCR decreases when OpEx increases by 25% or 40%."""
    base_df = run_df(seed=44)
    base_params = rmc_model.default_params()
    opex0 = float(base_params.get("operating_expenses_start", 0))
    shocked_df = run_df(seed=45 + int(bump * 100), overrides={"operating_expenses_start": opex0 * (1 + bump)})

    b = get_dscr_series(base_df)
    s = get_dscr_series(shocked_df)
    
    # Check that we have valid data
    assert len(b) > 0 and len(s) > 0, "DSCR series must not be empty"
    
    # Use tolerance for floating point comparison
    mean_diff = b.mean() - s.mean()
    median_diff = b.median() - s.median()
    
    assert mean_diff > 0.005, f"DSCR mean should drop significantly when OpEx +{int(bump*100)}% (diff={mean_diff:.6f})"
    assert median_diff > 0.001, f"DSCR median should drop when OpEx +{int(bump*100)}% (diff={median_diff:.6f})"


def test_coc_decreases_when_tax_rate_rises_100bps():
    """Test that CoC decreases when property tax rate increases by 100 basis points."""
    base_df = run_df(seed=46)
    base_params = rmc_model.default_params()
    tr = float(base_params.get("property_tax_rate", 0.0))
    shocked_df = run_df(seed=47, overrides={"property_tax_rate": tr + 0.010})

    b = get_coc_series(base_df)
    s = get_coc_series(shocked_df)
    
    # Check that we have valid data
    assert len(b) > 0 and len(s) > 0, "CoC series must not be empty"
    
    # Use tolerance for floating point comparison
    mean_diff = b.mean() - s.mean()
    median_diff = b.median() - s.median()
    
    assert mean_diff > 0.0005, f"CoC mean should drop when property tax +100 bps (diff={mean_diff:.6f})"
    assert median_diff > 0.0002, f"CoC median should drop when property tax +100 bps (diff={median_diff:.6f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])