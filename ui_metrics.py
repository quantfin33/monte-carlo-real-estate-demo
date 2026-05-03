"""
UI Metrics - Pure functions for Monte Carlo real estate model metrics calculation.

This module extracts all metric calculation logic from UI.py into pure functions
that accept a pandas DataFrame (simulation results) and return numeric outputs.

Functions:
- irr_stats(df) → dict: IRR mean, median, p5, p50, p95, prob_ge_15
- capex_adj_irr_mean(df) → float: Mean CapEx-adjusted IRR
- return_value_metrics(df) → dict: CoC, Equity Multiple, NPV, PI with percentiles
- risk_ops_metrics(df) → dict: YoC, CapRate, LTV, DSCR, etc.
- covenant_minima(df) → dict: Min DSCR, Min Debt Yield, WALT
- prepay_defeasance(df) → dict: Defeasance/prepay usage and costs
- operational_risk_metrics(df) → dict: GOI, Revenue Growth, Occupancy, etc.
- advanced_financial_metrics(df) → dict: FFO, AFFO, NAV
- financial_ratios_metrics(df) → dict: PI, Net Cash Flow, Price-to-Rent, etc.
- fifty_percent_rule_metrics(df) → dict: 50% Rule calculations
- reit_investment_metrics(df) → dict: FFO Payout Ratio, ROC, Investment Rating

All functions handle missing columns gracefully by returning math.nan for missing data.
"""

import warnings
from typing import Any

import numpy as np
import pandas as pd

from metrics_schema import (
    BACKWARD_COMPAT_ALIASES,
    add_backward_compat_aliases,
    create_percentile_stats,
)

# Module-level flag to emit warning only once
_backward_compat_warning_emitted = False


class _BackwardCompatDict(dict):
    """Dict subclass that warns when backward compatibility aliases are accessed."""

    def __init__(self, nested_result: dict[str, Any], aliases: dict[str, tuple[str, str]]):
        super().__init__(nested_result)
        self._aliases = aliases
        self._flat_keys = set(aliases.keys())

        # Add flat key values
        for flat_key, (parent_key, child_key) in aliases.items():
            if parent_key in nested_result and child_key in nested_result[parent_key]:
                super().__setitem__(flat_key, nested_result[parent_key][child_key])

    def __getitem__(self, key):
        global _backward_compat_warning_emitted

        if key in self._flat_keys and not _backward_compat_warning_emitted:
            warnings.warn(
                f"Accessing flat key '{key}' is deprecated. "
                f"Use nested structure: result['{self._aliases[key][0]}']['{self._aliases[key][1]}'] instead. "
                "Flat keys will be removed in v1.0.0.",
                DeprecationWarning,
                stacklevel=3
            )
            _backward_compat_warning_emitted = True

        return super().__getitem__(key)


def _safe_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Safely extract a numeric series from DataFrame, returning empty series if missing."""
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(dtype=float)


def _safe_percentiles(series: pd.Series, percentiles: tuple[float, ...] = (5, 50, 95)) -> tuple[float, ...]:
    """Calculate percentiles safely, returning NaN for invalid/empty series."""
    if series is None or series.empty:
        return tuple(float('nan') for _ in percentiles)

    clean_series = series.dropna()
    if clean_series.empty:
        return tuple(float('nan') for _ in percentiles)

    return tuple(float(np.percentile(clean_series, p)) for p in percentiles)


def _safe_mean(series: pd.Series) -> float:
    """Calculate mean safely, returning NaN for invalid/empty series."""
    if series is None or series.empty:
        return float('nan')

    clean_series = series.dropna()
    if clean_series.empty:
        return float('nan')

    return float(clean_series.mean())


def irr_stats(df: pd.DataFrame) -> dict[str, float]:
    """
    Calculate IRR statistics.
    
    Required columns: IRR
    Formula: Various statistics on IRR distribution
    Returns: dict with mean, median, p5, p50, p95, prob_ge_15
    Fallback: All NaN if IRR column missing
    """
    irr_series = _safe_series(df, 'IRR')

    if irr_series.empty:
        return {
            'mean': float('nan'),
            'median': float('nan'),
            'p5': float('nan'),
            'p50': float('nan'),
            'p95': float('nan'),
            'prob_ge_15': float('nan')
        }

    clean_irr = irr_series.dropna()
    if clean_irr.empty:
        return {
            'mean': float('nan'),
            'median': float('nan'),
            'p5': float('nan'),
            'p50': float('nan'),
            'p95': float('nan'),
            'prob_ge_15': float('nan')
        }

    p5, p50, p95 = _safe_percentiles(clean_irr, (5, 50, 95))

    # Align the definition of 'median' with the 50th percentile to avoid
    # tiny floating-point discrepancies on small samples.
    median_aligned = p50

    return {
        'mean': float(clean_irr.mean()),
        'median': float(median_aligned),
        'p5': p5,
        'p50': p50,
        'p95': p95,
        'prob_ge_15': float((clean_irr >= 0.15).mean())  # 15% threshold for IRR analysis
    }


def capex_adj_irr_mean(df: pd.DataFrame) -> float:
    """
    Calculate mean CapEx-adjusted IRR.
    
    Required columns: IRR_CapexAdj
    Formula: Mean of CapEx-adjusted IRR
    Returns: float mean or NaN if missing
    Fallback: NaN if column missing
    """
    capex_adj_irr = _safe_series(df, 'IRR_CapexAdj')
    return _safe_mean(capex_adj_irr)


def return_value_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate return and value metrics.
    
    Required columns: CoC, EquityMultiple, NPV, (PI or NPV+Equity for fallback)
    Formula: Percentiles and means for each metric
    Returns: dict with each metric's mean and percentiles
    Fallback: NaN for missing columns, calculate PI from NPV+Equity if PI missing
    """
    coc_series = _safe_series(df, 'CoC')
    em_series = _safe_series(df, 'EquityMultiple')
    npv_series = _safe_series(df, 'NPV')
    pi_series = _safe_series(df, 'PI')

    # PI fallback calculation if PI column missing but NPV and Equity available
    if pi_series.empty and not npv_series.empty:
        equity_series = _safe_series(df, 'Equity')
        if not equity_series.empty:
            # PI = (NPV + Equity) / Equity
            pi_series = (npv_series + equity_series) / equity_series
            pi_series = pi_series.replace([np.inf, -np.inf], np.nan)

    # Calculate stats for each metric
    coc_p5, coc_p50, coc_p95 = _safe_percentiles(coc_series)
    em_p5, em_p50, em_p95 = _safe_percentiles(em_series)
    npv_p5, npv_p50, npv_p95 = _safe_percentiles(npv_series)
    pi_p5, pi_p50, pi_p95 = _safe_percentiles(pi_series)

    # Create nested structure for canonical API
    nested_result = {
        'coc': create_percentile_stats(
            mean=_safe_mean(coc_series),
            p5=coc_p5,
            p50=coc_p50,
            p95=coc_p95
        ),
        'equity_multiple': create_percentile_stats(
            mean=_safe_mean(em_series),
            p5=em_p5,
            p50=em_p50,
            p95=em_p95
        ),
        'npv': create_percentile_stats(
            mean=_safe_mean(npv_series),
            p5=npv_p5,
            p50=npv_p50,
            p95=npv_p95
        ),
        'profitability_index': create_percentile_stats(
            mean=_safe_mean(pi_series),
            p5=pi_p5,
            p50=pi_p50,
            p95=pi_p95
        )
    }

    # Add backward compatibility aliases with deprecation warnings
    return _BackwardCompatDict(nested_result, BACKWARD_COMPAT_ALIASES)


def risk_ops_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate risk and operations metrics.
    
    Required columns: YieldOnCost, CapRate, LTV, DSCR_Y1/DSCR, BreakEvenOcc, 
                     DebtYield_Y1, Stabilized_YoC, RunStableAllYears, YearsBelowBreakeven
    Formula: Various risk and operational metrics
    Returns: dict with risk metrics values
    Fallback: NaN for missing columns, DSCR fallback to DSCR_Y1 if MinDSCR missing
    """
    yoc_series = _safe_series(df, 'YieldOnCost')
    caprate_series = _safe_series(df, 'CapRate')
    ltv_series = _safe_series(df, 'LTV')

    # DSCR with fallback
    dscr_series = _safe_series(df, 'DSCR_Y1')
    if dscr_series.empty:
        dscr_series = _safe_series(df, 'DSCR')

    breakeven_series = _safe_series(df, 'BreakEvenOcc')
    debt_yield_series = _safe_series(df, 'DebtYield_Y1')
    stabilized_yoc_series = _safe_series(df, 'Stabilized_YoC')
    stable_all_years_series = _safe_series(df, 'RunStableAllYears')
    years_below_breakeven_series = _safe_series(df, 'YearsBelowBreakeven')

    # Calculate percentiles for each metric
    yoc_p5, yoc_p50, yoc_p95 = _safe_percentiles(yoc_series)
    caprate_p5, caprate_p50, caprate_p95 = _safe_percentiles(caprate_series)
    ltv_p5, ltv_p50, ltv_p95 = _safe_percentiles(ltv_series)
    dscr_p5, dscr_p50, dscr_p95 = _safe_percentiles(dscr_series)
    breakeven_p5, breakeven_p50, breakeven_p95 = _safe_percentiles(breakeven_series)
    debt_yield_p5, debt_yield_p50, debt_yield_p95 = _safe_percentiles(debt_yield_series)

    # Calculate percentage for stable all years (boolean to percentage)
    stable_all_years_pct = float('nan')
    if not stable_all_years_series.empty:
        stable_clean = stable_all_years_series.dropna()
        if not stable_clean.empty:
            stable_all_years_pct = float((stable_clean == True).mean() * 100.0)

    # Create nested structure for canonical API
    nested_result = {
        'yoc': create_percentile_stats(
            mean=_safe_mean(yoc_series),
            p5=yoc_p5,
            p50=yoc_p50,
            p95=yoc_p95
        ),
        'cap_rate': create_percentile_stats(
            mean=_safe_mean(caprate_series),
            p5=caprate_p5,
            p50=caprate_p50,
            p95=caprate_p95
        ),
        'ltv': create_percentile_stats(
            mean=_safe_mean(ltv_series),
            p5=ltv_p5,
            p50=ltv_p50,
            p95=ltv_p95
        ),
        'dscr': create_percentile_stats(
            mean=_safe_mean(dscr_series),
            p5=dscr_p5,
            p50=dscr_p50,
            p95=dscr_p95
        ),
        'breakeven_occ': create_percentile_stats(
            mean=_safe_mean(breakeven_series),
            p5=breakeven_p5,
            p50=breakeven_p50,
            p95=breakeven_p95
        ),
        'debt_yield_y1': create_percentile_stats(
            mean=_safe_mean(debt_yield_series),
            p5=debt_yield_p5,
            p50=debt_yield_p50,
            p95=debt_yield_p95
        )
    }

    # Add flat compatibility keys for legacy code
    risk_compat_aliases = {
        'yoc_mean': ('yoc', 'mean'),
        'caprate_mean': ('cap_rate', 'mean'),
        'ltv_mean': ('ltv', 'mean'),
        'dscr_y1_mean': ('dscr', 'mean'),
        'breakeven_occ_mean': ('breakeven_occ', 'mean'),
        'debt_yield_y1_mean': ('debt_yield_y1', 'mean'),
        'stabilized_yoc_mean': ('yoc', 'mean'),  # Fallback to yoc
        'run_stable_all_years_pct': ('stable_all_years_pct', 'value'),
        'years_below_breakeven_mean': ('years_below_breakeven', 'mean'),
    }

    result = add_backward_compat_aliases(nested_result, risk_compat_aliases)

    # Add special values not in percentile structure
    result['stabilized_yoc_mean'] = _safe_mean(stabilized_yoc_series)
    result['run_stable_all_years_pct'] = stable_all_years_pct
    result['years_below_breakeven_mean'] = _safe_mean(years_below_breakeven_series)

    return result


def covenant_minima(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate covenant minimum metrics.
    
    Required columns: MinDSCR/DSCR_Min/DSCR, MinDebtYield/DebtYield_Min/DebtYield_Y1, WALT
    Formula: Min covenant metrics with percentiles
    Returns: dict with min_dscr and min_debt_yield stats, plus WALT
    Fallback: Try multiple column name variations, use Y1 values if min not available
    """
    # Find minimum DSCR series with fallbacks
    min_dscr_series = None
    for col in ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr"]:
        if col in df.columns:
            min_dscr_series = _safe_series(df, col)
            break
    if min_dscr_series is None or min_dscr_series.empty:
        min_dscr_series = _safe_series(df, 'DSCR')

    # Find minimum debt yield series with fallbacks
    min_dy_series = None
    for col in ["MinDebtYield", "DebtYield_Min", "min_dy", "mindebtyield"]:
        if col in df.columns:
            min_dy_series = _safe_series(df, col)
            break
    if min_dy_series is None or min_dy_series.empty:
        min_dy_series = _safe_series(df, 'DebtYield_Y1')

    walt_series = _safe_series(df, 'WALT')

    # Calculate percentiles
    dscr_p5, dscr_p50, dscr_p95 = _safe_percentiles(min_dscr_series)
    dy_p5, dy_p50, dy_p95 = _safe_percentiles(min_dy_series)

    return {
        'min_dscr_mean': _safe_mean(min_dscr_series),
        'min_dscr_p5': dscr_p5,
        'min_dscr_p50': dscr_p50,
        'min_dscr_p95': dscr_p95,
        'min_dy_mean_pct': _safe_mean(min_dy_series) * 100.0 if not min_dy_series.empty else float('nan'),
        'min_dy_p5': dy_p5,
        'min_dy_p50': dy_p50,
        'min_dy_p95': dy_p95,
        'walt_mean': _safe_mean(walt_series)
    }


def prepay_defeasance(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate prepayment and defeasance metrics.
    
    Required columns: Defeasance_Used, Defeasance_Cost_Refi, Prepay_Cost_Sale, 
                     PrepayAtSale_Used, PrepayAtSale_Toggle, Prepay_Model
    Formula: Usage percentages and average costs when used
    Returns: dict with usage percentages and costs
    Fallback: 0.0 for missing boolean columns, NaN for missing cost columns
    """
    # Defeasance usage
    def_used_series = _safe_series(df, 'Defeasance_Used')
    def_used_pct = 0.0
    if not def_used_series.empty:
        def_used_pct = float((def_used_series == True).mean() * 100.0)

    # Defeasance cost when used
    def_cost_series = _safe_series(df, 'Defeasance_Cost_Refi')
    avg_def_cost = float('nan')
    if not def_cost_series.empty and not def_used_series.empty:
        used_mask = (def_used_series == True)
        if used_mask.sum() > 0:
            avg_def_cost = float(def_cost_series[used_mask].mean())

    # Prepay at sale usage (prefer cost > 0 method)
    prepay_cost_series = _safe_series(df, 'Prepay_Cost_Sale')
    sale_used_pct = 0.0
    if not prepay_cost_series.empty:
        sale_used_pct = float((prepay_cost_series > 1e-6).mean() * 100.0)
    else:
        prepay_used_series = _safe_series(df, 'PrepayAtSale_Used')
        if not prepay_used_series.empty:
            sale_used_pct = float((prepay_used_series == True).mean() * 100.0)

    # Average prepay cost when used
    avg_prepay_cost = float('nan')
    if not prepay_cost_series.empty:
        used_mask = (prepay_cost_series > 1e-6)
        if used_mask.sum() > 0:
            avg_prepay_cost = float(prepay_cost_series[used_mask].mean())

    # Toggle percentage
    toggle_series = _safe_series(df, 'PrepayAtSale_Toggle')
    toggle_on_pct = 0.0
    if not toggle_series.empty:
        toggle_on_pct = float((toggle_series == True).mean() * 100.0)

    # Most common prepay model
    prepay_model_series = df.get('Prepay_Model', pd.Series(dtype=object))
    most_common_model = "(n/a)"
    if not prepay_model_series.empty:
        try:
            mode_result = prepay_model_series.mode()
            if len(mode_result) > 0:
                most_common_model = str(mode_result.iloc[0])
        except Exception:
            most_common_model = "(n/a)"

    return {
        'defeasance_used_pct': def_used_pct,
        'avg_def_cost_when_used': avg_def_cost,
        'prepay_sale_used_pct': sale_used_pct,
        'avg_prepay_sale_cost_when_used': avg_prepay_cost,
        'toggle_on_pct': toggle_on_pct,
        'most_common_model': most_common_model
    }


def operational_risk_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate operational and risk metrics.
    
    Required columns: GOI, AAR, RevenueGrowth_YoY, OccupancyRate, TenantTurnoverRate,
                     AvgRentPricePSF, LeaseRenewalRate, ConstructionCostPSF, 
                     PaybackPeriod, AvgCommissionPerSale, RiskAssessmentScore
    Formula: Percentiles for operational metrics
    Returns: dict with all operational metrics and percentiles
    Fallback: NaN for missing columns
    """
    # Extract all series
    goi_series = _safe_series(df, 'GOI')
    aar_series = _safe_series(df, 'AAR')
    revenue_growth_series = _safe_series(df, 'RevenueGrowth_YoY')
    occ_rate_series = _safe_series(df, 'OccupancyRate')
    turnover_series = _safe_series(df, 'TenantTurnoverRate')
    avg_rent_series = _safe_series(df, 'AvgRentPricePSF')
    renewal_rate_series = _safe_series(df, 'LeaseRenewalRate')
    construction_cost_series = _safe_series(df, 'ConstructionCostPSF')
    payback_series = _safe_series(df, 'PaybackPeriod')
    commission_series = _safe_series(df, 'AvgCommissionPerSale')
    risk_score_series = _safe_series(df, 'RiskAssessmentScore')

    # Calculate percentiles for each
    goi_p5, goi_p50, goi_p95 = _safe_percentiles(goi_series)
    aar_p5, aar_p50, aar_p95 = _safe_percentiles(aar_series)
    rev_growth_p5, rev_growth_p50, rev_growth_p95 = _safe_percentiles(revenue_growth_series)
    occ_p5, occ_p50, occ_p95 = _safe_percentiles(occ_rate_series)
    turnover_p5, turnover_p50, turnover_p95 = _safe_percentiles(turnover_series)
    rent_p5, rent_p50, rent_p95 = _safe_percentiles(avg_rent_series)
    renewal_p5, renewal_p50, renewal_p95 = _safe_percentiles(renewal_rate_series)
    construction_p5, construction_p50, construction_p95 = _safe_percentiles(construction_cost_series)
    payback_p5, payback_p50, payback_p95 = _safe_percentiles(payback_series)
    commission_p5, commission_p50, commission_p95 = _safe_percentiles(commission_series)
    risk_p5, risk_p50, risk_p95 = _safe_percentiles(risk_score_series)

    return {
        'goi_p5': goi_p5, 'goi_p50': goi_p50, 'goi_p95': goi_p95,
        'aar_p5': aar_p5, 'aar_p50': aar_p50, 'aar_p95': aar_p95,
        'revenue_growth_p5': rev_growth_p5, 'revenue_growth_p50': rev_growth_p50, 'revenue_growth_p95': rev_growth_p95,
        'occupancy_rate_p5': occ_p5, 'occupancy_rate_p50': occ_p50, 'occupancy_rate_p95': occ_p95,
        'tenant_turnover_p5': turnover_p5, 'tenant_turnover_p50': turnover_p50, 'tenant_turnover_p95': turnover_p95,
        'avg_rent_psf_p5': rent_p5, 'avg_rent_psf_p50': rent_p50, 'avg_rent_psf_p95': rent_p95,
        'lease_renewal_p5': renewal_p5, 'lease_renewal_p50': renewal_p50, 'lease_renewal_p95': renewal_p95,
        'construction_cost_p5': construction_p5, 'construction_cost_p50': construction_p50, 'construction_cost_p95': construction_p95,
        'payback_period_p5': payback_p5, 'payback_period_p50': payback_p50, 'payback_period_p95': payback_p95,
        'commission_p5': commission_p5, 'commission_p50': commission_p50, 'commission_p95': commission_p95,
        'risk_score_p5': risk_p5, 'risk_score_p50': risk_p50, 'risk_score_p95': risk_p95
    }


def advanced_financial_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate advanced financial metrics.
    
    Required columns: FFO, AFFO, NAV
    Formula: Percentiles for advanced financial metrics
    Returns: dict with FFO, AFFO, NAV percentiles
    Fallback: NaN for missing columns
    """
    ffo_series = _safe_series(df, 'FFO')
    affo_series = _safe_series(df, 'AFFO')
    nav_series = _safe_series(df, 'NAV')

    ffo_p5, ffo_p50, ffo_p95 = _safe_percentiles(ffo_series)
    affo_p5, affo_p50, affo_p95 = _safe_percentiles(affo_series)
    nav_p5, nav_p50, nav_p95 = _safe_percentiles(nav_series)

    return {
        'ffo_p5': ffo_p5, 'ffo_p50': ffo_p50, 'ffo_p95': ffo_p95,
        'affo_p5': affo_p5, 'affo_p50': affo_p50, 'affo_p95': affo_p95,
        'nav_p5': nav_p5, 'nav_p50': nav_p50, 'nav_p95': nav_p95
    }


def financial_ratios_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate financial ratios and performance metrics.
    
    Required columns: PI, NetCashFlow, PriceToRentRatio, GrossRentalYield, DebtToEquityRatio,
                     CoC, BreakEvenOcc, NOI_Y1, RentToCostRatio, ReturnOnEquity
    Formula: Percentiles for financial ratio metrics
    Returns: dict with all financial ratio percentiles
    Fallback: NaN for missing columns
    """
    # Core ratios
    pi_series = _safe_series(df, 'PI')
    net_cash_flow_series = _safe_series(df, 'NetCashFlow')
    price_to_rent_series = _safe_series(df, 'PriceToRentRatio')
    gross_rental_yield_series = _safe_series(df, 'GrossRentalYield')
    debt_to_equity_series = _safe_series(df, 'DebtToEquityRatio')

    # Additional metrics that should be in financial ratios section
    coc_series = _safe_series(df, 'CoC')
    breakeven_series = _safe_series(df, 'BreakEvenOcc')
    noi_series = _safe_series(df, 'NOI_Y1')
    rent_to_cost_series = _safe_series(df, 'RentToCostRatio')
    return_on_equity_series = _safe_series(df, 'ReturnOnEquity')

    # Calculate percentiles
    pi_p5, pi_p50, pi_p95 = _safe_percentiles(pi_series)
    ncf_p5, ncf_p50, ncf_p95 = _safe_percentiles(net_cash_flow_series)
    ptr_p5, ptr_p50, ptr_p95 = _safe_percentiles(price_to_rent_series)
    gry_p5, gry_p50, gry_p95 = _safe_percentiles(gross_rental_yield_series)
    dte_p5, dte_p50, dte_p95 = _safe_percentiles(debt_to_equity_series)

    coc_p5, coc_p50, coc_p95 = _safe_percentiles(coc_series)
    be_p5, be_p50, be_p95 = _safe_percentiles(breakeven_series)
    noi_p5, noi_p50, noi_p95 = _safe_percentiles(noi_series)
    rtc_p5, rtc_p50, rtc_p95 = _safe_percentiles(rent_to_cost_series)
    roe_p5, roe_p50, roe_p95 = _safe_percentiles(return_on_equity_series)

    return {
        'pi_p5': pi_p5, 'pi_p50': pi_p50, 'pi_p95': pi_p95,
        'net_cash_flow_p5': ncf_p5, 'net_cash_flow_p50': ncf_p50, 'net_cash_flow_p95': ncf_p95,
        'price_to_rent_p5': ptr_p5, 'price_to_rent_p50': ptr_p50, 'price_to_rent_p95': ptr_p95,
        'gross_rental_yield_p5': gry_p5, 'gross_rental_yield_p50': gry_p50, 'gross_rental_yield_p95': gry_p95,
        'debt_to_equity_p5': dte_p5, 'debt_to_equity_p50': dte_p50, 'debt_to_equity_p95': dte_p95,
        'coc_p5': coc_p5, 'coc_p50': coc_p50, 'coc_p95': coc_p95,
        'breakeven_occ_p5': be_p5, 'breakeven_occ_p50': be_p50, 'breakeven_occ_p95': be_p95,
        'noi_p5': noi_p5, 'noi_p50': noi_p50, 'noi_p95': noi_p95,
        'rent_to_cost_p5': rtc_p5, 'rent_to_cost_p50': rtc_p50, 'rent_to_cost_p95': rtc_p95,
        'return_on_equity_p5': roe_p5, 'return_on_equity_p50': roe_p50, 'return_on_equity_p95': roe_p95
    }


def fifty_percent_rule_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate 50% Rule metrics.
    
    Required columns: FiftyPercentRule_Ratio, FiftyPercentRule_Pass, FiftyPercentRule_TotalExpenses
    Formula: 50% Rule analysis percentiles and pass rate
    Returns: dict with 50% rule metrics
    Fallback: NaN for missing columns
    """
    ratio_series = _safe_series(df, 'FiftyPercentRule_Ratio')
    pass_series = _safe_series(df, 'FiftyPercentRule_Pass')
    expenses_series = _safe_series(df, 'FiftyPercentRule_TotalExpenses')

    # Calculate pass percentage
    pass_pct = float('nan')
    if not pass_series.empty:
        clean_pass = pass_series.dropna()
        if not clean_pass.empty:
            pass_pct = float((clean_pass == True).mean() * 100.0)

    ratio_p5, ratio_p50, ratio_p95 = _safe_percentiles(ratio_series)
    exp_p5, exp_p50, exp_p95 = _safe_percentiles(expenses_series)

    return {
        'fifty_percent_ratio_p5': ratio_p5,
        'fifty_percent_ratio_p50': ratio_p50,
        'fifty_percent_ratio_p95': ratio_p95,
        'fifty_percent_pass_pct': pass_pct,
        'fifty_percent_expenses_p5': exp_p5,
        'fifty_percent_expenses_p50': exp_p50,
        'fifty_percent_expenses_p95': exp_p95
    }


def reit_investment_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate REIT and investment analysis metrics.
    
    Required columns: FFO_PayoutRatio, ReturnOnCost, InvestmentRating
    Formula: Percentiles for REIT analysis metrics
    Returns: dict with REIT metrics percentiles and validity percentages
    Fallback: NaN for missing columns
    """
    ffo_payout_series = _safe_series(df, 'FFO_PayoutRatio')
    roc_series = _safe_series(df, 'ReturnOnCost')
    rating_series = _safe_series(df, 'InvestmentRating')

    # Calculate validity percentages (non-NaN data)
    ffo_valid_pct = 0.0
    roc_valid_pct = 0.0
    rating_valid_pct = 0.0

    if not ffo_payout_series.empty:
        ffo_valid_pct = float((~ffo_payout_series.isna()).mean() * 100.0)

    if not roc_series.empty:
        roc_valid_pct = float((~roc_series.isna()).mean() * 100.0)

    if not rating_series.empty:
        rating_valid_pct = float((~rating_series.isna()).mean() * 100.0)

    # Calculate percentiles
    ffo_p5, ffo_p50, ffo_p95 = _safe_percentiles(ffo_payout_series)
    roc_p5, roc_p50, roc_p95 = _safe_percentiles(roc_series)
    rating_p5, rating_p50, rating_p95 = _safe_percentiles(rating_series)

    return {
        'ffo_payout_p5': ffo_p5,
        'ffo_payout_p50': ffo_p50,
        'ffo_payout_p95': ffo_p95,
        'ffo_payout_valid_pct': ffo_valid_pct,
        'return_on_cost_p5': roc_p5,
        'return_on_cost_p50': roc_p50,
        'return_on_cost_p95': roc_p95,
        'return_on_cost_valid_pct': roc_valid_pct,
        'investment_rating_p5': rating_p5,
        'investment_rating_p50': rating_p50,
        'investment_rating_p95': rating_p95,
        'investment_rating_valid_pct': rating_valid_pct
    }


def additional_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate additional KPI metrics.
    
    Required columns: GRM, OperatingExpenseRatio, EquityToValue, InterestCoverage, ROI, Capex_Total
    Formula: Percentiles for additional KPIs
    Returns: dict with additional KPI percentiles
    Fallback: NaN for missing columns
    """
    grm_series = _safe_series(df, 'GRM')
    oer_series = _safe_series(df, 'OperatingExpenseRatio')
    e2v_series = _safe_series(df, 'EquityToValue')
    icr_series = _safe_series(df, 'InterestCoverage')
    roi_series = _safe_series(df, 'ROI')
    capx_series = _safe_series(df, 'Capex_Total')

    grm_p5, grm_p50, grm_p95 = _safe_percentiles(grm_series)
    oer_p5, oer_p50, oer_p95 = _safe_percentiles(oer_series)
    e2v_p5, e2v_p50, e2v_p95 = _safe_percentiles(e2v_series)
    icr_p5, icr_p50, icr_p95 = _safe_percentiles(icr_series)
    roi_p5, roi_p50, roi_p95 = _safe_percentiles(roi_series)
    capx_p5, capx_p50, capx_p95 = _safe_percentiles(capx_series)

    return {
        'grm_p5': grm_p5, 'grm_p50': grm_p50, 'grm_p95': grm_p95,
        'oer_p5': oer_p5, 'oer_p50': oer_p50, 'oer_p95': oer_p95,
        'equity_to_value_p5': e2v_p5, 'equity_to_value_p50': e2v_p50, 'equity_to_value_p95': e2v_p95,
        'interest_coverage_p5': icr_p5, 'interest_coverage_p50': icr_p50, 'interest_coverage_p95': icr_p95,
        'roi_p5': roi_p5, 'roi_p50': roi_p50, 'roi_p95': roi_p95,
        'capex_total_p5': capx_p5, 'capex_total_p50': capx_p50, 'capex_total_p95': capx_p95
    }
