from __future__ import annotations

import numpy as np
import pandas as pd

import engine_output_contract as contract
import rmc_model


def _run_df(params: dict | None = None, *, n: int = 120, seed: int = 42) -> pd.DataFrame:
    base = rmc_model.default_params()
    merged = {**base, **(params or {})}
    return rmc_model.run_simulation(n=n, seed=seed, params=merged, parallel=True)


def _finite_series(df: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(df[name], errors="coerce").dropna()


class TestAnnualValidatedOutputContract:
    def test_required_columns_present(self):
        df = _run_df()
        for name in contract.REQUIRED_ANNUAL_VALIDATED_COLUMNS:
            assert name in df.columns, f"Missing required raw output column: {name}"

    def test_required_columns_respect_nullability(self):
        df = _run_df()
        for name, spec in contract.REQUIRED_ANNUAL_VALIDATED_COLUMNS.items():
            series = pd.to_numeric(df[name], errors="coerce")
            finite = series.dropna()
            if not spec.nullable:
                assert not series.isna().any(), f"{name} is documented non-null but contains null values"
            assert np.isfinite(finite).all(), f"{name} contains non-finite numeric values"

    def test_bounds(self):
        df = _run_df()

        exit_cap = _finite_series(df, "ExitCap")
        assert (exit_cap > 0).all()

        capex_total = _finite_series(df, "Capex_Total")
        assert (capex_total >= 0).all()

        for name in ["PhysicalOccupancyRate", "EconomicOccupancyRate", "LeaseRenewalRate"]:
            series = _finite_series(df, name)
            assert ((series >= 0) & (series <= 1)).all(), f"{name} out of bounds"

    def test_higher_in_place_rent_lowers_grm(self):
        low = _run_df(params={"in_place_rent_psf": 18.0, "vacancy_auto_lease": False}, n=160, seed=101)
        high = _run_df(params={"in_place_rent_psf": 30.0, "vacancy_auto_lease": False}, n=160, seed=101)

        low_grm = float(np.nanmedian(pd.to_numeric(low["GRM"], errors="coerce")))
        high_grm = float(np.nanmedian(pd.to_numeric(high["GRM"], errors="coerce")))
        assert high_grm < low_grm

    def test_higher_opex_raises_oer(self):
        low = _run_df(params={"operating_expenses_start": 2_000_000}, n=160, seed=102)
        high = _run_df(params={"operating_expenses_start": 4_000_000}, n=160, seed=102)

        low_oer = float(np.nanmedian(pd.to_numeric(low["OperatingExpenseRatio"], errors="coerce")))
        high_oer = float(np.nanmedian(pd.to_numeric(high["OperatingExpenseRatio"], errors="coerce")))
        assert high_oer > low_oer

    def test_higher_debt_ratio_lowers_equity_to_value(self):
        low = _run_df(params={"debt_ratio": 0.30}, n=160, seed=103)
        high = _run_df(params={"debt_ratio": 0.70}, n=160, seed=103)

        low_e2v = float(np.nanmedian(pd.to_numeric(low["EquityToValue"], errors="coerce")))
        high_e2v = float(np.nanmedian(pd.to_numeric(high["EquityToValue"], errors="coerce")))
        assert high_e2v < low_e2v

    def test_higher_reserve_per_rsf_raises_capex_total(self):
        low = _run_df(params={"reserve_per_rsf": 0.0}, n=160, seed=104)
        high = _run_df(params={"reserve_per_rsf": 2.0}, n=160, seed=104)

        low_capex = float(np.nanmedian(pd.to_numeric(low["Capex_Total"], errors="coerce")))
        high_capex = float(np.nanmedian(pd.to_numeric(high["Capex_Total"], errors="coerce")))
        assert high_capex > low_capex

    def test_higher_initial_occupancy_raises_physical_occupancy(self):
        shared = {"vacancy_auto_lease": False}
        low = _run_df(params={**shared, "initial_occupancy": 0.60}, n=160, seed=105)
        high = _run_df(params={**shared, "initial_occupancy": 0.90}, n=160, seed=105)

        low_phys = float(np.nanmedian(pd.to_numeric(low["PhysicalOccupancyRate"], errors="coerce")))
        high_phys = float(np.nanmedian(pd.to_numeric(high["PhysicalOccupancyRate"], errors="coerce")))
        assert high_phys > low_phys

    def test_higher_renew_prob_raises_lease_renewal_rate(self):
        shared = {"walt_years": 1.0}
        low = _run_df(params={**shared, "renew_prob": 0.10}, n=200, seed=106)
        high = _run_df(params={**shared, "renew_prob": 0.90}, n=200, seed=106)

        low_rr = float(np.nanmedian(pd.to_numeric(low["LeaseRenewalRate"], errors="coerce")))
        high_rr = float(np.nanmedian(pd.to_numeric(high["LeaseRenewalRate"], errors="coerce")))
        assert high_rr > low_rr
