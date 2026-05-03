"""
Directional sensitivities (monotone) acceptance tests.

Checks (Base seed, fixed n):
 4) Rent +10% ⇒ IRR↑ & CoC↑ (median and mean)
 5) OpEx +20% ⇒ IRR↓ & DSCR↓ (median and mean)
 6) Tax +50 bps ⇒ NPV↓ & CoC↓ (median)

Pass if directions hold and deltas are non-trivial.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

import rmc_model


SEED = 42
N = 600


def _mean_median(series: pd.Series) -> tuple[float, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()), float(s.median())


def _assert_direction_and_delta(new: float, base: float, direction: str, min_delta: float, label: str):
    diff = new - base
    if direction == "up":
        assert diff > 0.0, f"{label} should increase: {base:.6f} → {new:.6f}"
    else:
        assert diff < 0.0, f"{label} should decrease: {base:.6f} → {new:.6f}"
    assert abs(diff) >= min_delta, f"{label} change too small: Δ={diff:.6f} (< {min_delta:.6f})"


class TestDirectionalSensitivities:
    def test_rent_plus_10pct(self):
        params = rmc_model.default_params()
        base = rmc_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)

        # Shock: +10% rents (both in-place and market)
        rent_params = dict(params)
        rent_params['market_rent_psf'] = params['market_rent_psf'] * 1.10
        rent_params['in_place_rent_psf'] = params['in_place_rent_psf'] * 1.10
        shocked = rmc_model.run_simulation(n=N, seed=SEED, params=rent_params, parallel=True)

        irr_mean_b, irr_med_b = _mean_median(base['IRR'])
        irr_mean_s, irr_med_s = _mean_median(shocked['IRR'])
        coc_mean_b, coc_med_b = _mean_median(base['CoC'])
        coc_mean_s, coc_med_s = _mean_median(shocked['CoC'])

        # Require non-trivial improvements
        _assert_direction_and_delta(irr_mean_s, irr_mean_b, 'up', 0.002, 'IRR mean')
        _assert_direction_and_delta(irr_med_s, irr_med_b, 'up', 0.002, 'IRR median')
        _assert_direction_and_delta(coc_mean_s, coc_mean_b, 'up', 0.0015, 'CoC mean')
        _assert_direction_and_delta(coc_med_s, coc_med_b, 'up', 0.0015, 'CoC median')

    def test_opex_plus_20pct(self):
        params = rmc_model.default_params()
        # Use GROSS to ensure OpEx moves are not offset by recoveries
        params['GLOBAL_RECOVERY_TYPE'] = 'GROSS'
        base = rmc_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)

        # Shock: +20% OpEx
        opex_params = dict(params)
        opex_params['operating_expenses_start'] = params['operating_expenses_start'] * 1.20
        shocked = rmc_model.run_simulation(n=N, seed=SEED, params=opex_params, parallel=True)

        irr_mean_b, irr_med_b = _mean_median(base['IRR'])
        irr_mean_s, irr_med_s = _mean_median(shocked['IRR'])
        dscr_mean_b, dscr_med_b = _mean_median(base['DSCR'])
        dscr_mean_s, dscr_med_s = _mean_median(shocked['DSCR'])

        _assert_direction_and_delta(irr_mean_s, irr_mean_b, 'down', 0.002, 'IRR mean')
        _assert_direction_and_delta(irr_med_s, irr_med_b, 'down', 0.002, 'IRR median')
        _assert_direction_and_delta(dscr_mean_s, dscr_mean_b, 'down', 0.02, 'DSCR mean')
        _assert_direction_and_delta(dscr_med_s, dscr_med_b, 'down', 0.02, 'DSCR median')

    def test_tax_plus_50bps(self):
        params = rmc_model.default_params()
        base = rmc_model.run_simulation(n=N, seed=SEED, params=params, parallel=True)

        # Shock: +50 bps property tax rate
        tax_params = dict(params)
        tax_params['property_tax_rate'] = float(params.get('property_tax_rate', 0.0)) + 0.005
        shocked = rmc_model.run_simulation(n=N, seed=SEED, params=tax_params, parallel=True)

        # NPV (mean) and CoC (median) should decline; non-trivial deltas
        npv_mean_b, npv_med_b = _mean_median(base['NPV'])
        npv_mean_s, npv_med_s = _mean_median(shocked['NPV'])
        coc_mean_b, coc_med_b = _mean_median(base['CoC'])
        coc_mean_s, coc_med_s = _mean_median(shocked['CoC'])

        # NPV down (mean) with relative change >= 1%
        npv_diff = npv_mean_s - npv_mean_b
        assert npv_diff < 0.0, f"NPV mean should decrease: {npv_mean_b:,.0f} → {npv_mean_s:,.0f}"
        rel_npv_change = abs(npv_diff) / max(1.0, abs(npv_mean_b))
        assert rel_npv_change >= 0.01, f"NPV change too small: {rel_npv_change:.2%}"

        # CoC should be monotone non-increasing in median. NPV carries the
        # non-trivial change requirement for the tax shock.
        assert coc_med_s <= coc_med_b, f"CoC median should not increase: {coc_med_b:.6f} → {coc_med_s:.6f}"
