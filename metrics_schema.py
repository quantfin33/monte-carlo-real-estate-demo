"""
Canonical metrics schema with TypedDicts for Monte Carlo real estate model.

Defines the standard structure and keys for all metric function returns.
This ensures API consistency and enables proper type checking.

Key Design Principles:
- Snake_case keys for consistency
- Nested structure for related metrics (percentiles grouped under parent)
- Backward compatibility aliases where needed
- NaN values for missing/incalculable data
"""

from typing import Any, NotRequired, TypedDict


class PercentileStats(TypedDict):
    """Standard percentile statistics structure."""
    mean: float
    p5: float   # 5th percentile
    p50: float  # 50th percentile (median)
    p95: float  # 95th percentile


class IRRStatsTD(TypedDict):
    """IRR statistics with probabilities."""
    irr: PercentileStats
    prob_ge_15pct: float  # Probability IRR >= 15%
    prob_ge_20pct: NotRequired[float]  # Optional: Probability IRR >= 20%


class ReturnValueTD(TypedDict):
    """Return and value metrics with canonical keys."""
    coc: PercentileStats  # Cash-on-Cash return (canonical key for tests)
    equity_multiple: PercentileStats
    npv: PercentileStats
    profitability_index: PercentileStats  # PI = (NPV + Equity) / Equity
    # Backward compatibility aliases (temporary)
    cash_on_cash: NotRequired[PercentileStats]  # Deprecated alias for 'coc'


class RiskOpsTD(TypedDict):
    """Risk and operations metrics."""
    yoc: PercentileStats  # Yield on Cost
    cap_rate: PercentileStats  # Capitalization Rate
    ltv: PercentileStats  # Loan-to-Value
    dscr: PercentileStats  # Debt Service Coverage Ratio
    breakeven_occ: PercentileStats  # Breakeven Occupancy
    debt_yield_y1: PercentileStats  # Year 1 Debt Yield
    stabilized_yoc: NotRequired[PercentileStats]  # Optional stabilized YoC


class CovenantMinimaTD(TypedDict):
    """Covenant and minimum threshold metrics."""
    min_dscr_p05: float
    min_dscr_p50: float
    min_dscr_p95: float
    min_dy_p05: float  # Minimum Debt Yield
    min_dy_p50: float
    min_dy_p95: float
    min_dscr_avg: float
    min_dy_avg: float
    walt: NotRequired[float]  # Weighted Average Lease Term


class PrepayDefeasanceTD(TypedDict):
    """Prepayment and defeasance metrics."""
    defeasance_used_pct: float  # Percentage using defeasance
    prepay_sale_used_pct: float  # Percentage using prepayment at sale
    avg_defeasance_cost: float
    avg_prepay_cost: float
    prepay_toggle_on_pct: float  # Percentage with prepay toggle enabled
    most_common_prepay_model: str  # Most frequently used prepay model


class OperationalRiskTD(TypedDict):
    """Operational and risk metrics."""
    goi: PercentileStats  # Gross Operating Income
    revenue_growth: PercentileStats
    occupancy: PercentileStats
    tenant_turnover: NotRequired[PercentileStats]
    avg_rent_psf: NotRequired[PercentileStats]
    renewal_rate: NotRequired[PercentileStats]


class AdvancedFinancialTD(TypedDict):
    """Advanced financial metrics (FFO, AFFO, NAV)."""
    ffo: PercentileStats  # Funds From Operations
    affo: PercentileStats  # Adjusted Funds From Operations
    nav: PercentileStats  # Net Asset Value
    depreciation_expense: NotRequired[PercentileStats]


class FinancialRatiosTD(TypedDict):
    """Financial ratios and derived metrics."""
    pi: PercentileStats  # Profitability Index
    net_cash_flow: PercentileStats
    price_to_rent: PercentileStats
    construction_cost_psf: NotRequired[PercentileStats]
    payback_period: NotRequired[PercentileStats]


class FiftyPercentRuleTD(TypedDict):
    """50% Rule metrics and calculations."""
    fifty_percent_rule_ratio: float
    fifty_percent_rule_pass: bool
    fifty_percent_rule_expenses: float


class REITInvestmentTD(TypedDict):
    """REIT-specific investment metrics."""
    ffo_payout_ratio: PercentileStats
    return_on_cost: PercentileStats
    investment_rating: PercentileStats
    risk_score: NotRequired[PercentileStats]


# Alias mapping for backward compatibility
# Maps old flat keys to new nested paths
BACKWARD_COMPAT_ALIASES = {
    # Old flat keys -> new nested structure
    'coc_mean': ('coc', 'mean'),
    'coc_p5': ('coc', 'p5'),
    'coc_p50': ('coc', 'p50'),
    'coc_p95': ('coc', 'p95'),
    'cash_on_cash_mean': ('coc', 'mean'),  # Legacy alias
    'cash_on_cash_p5': ('coc', 'p5'),
    'cash_on_cash_p50': ('coc', 'p50'),
    'cash_on_cash_p95': ('coc', 'p95'),
    'equity_multiple_mean': ('equity_multiple', 'mean'),
    'equity_multiple_p5': ('equity_multiple', 'p5'),
    'equity_multiple_p50': ('equity_multiple', 'p50'),
    'equity_multiple_p95': ('equity_multiple', 'p95'),
    'npv_mean': ('npv', 'mean'),
    'npv_p5': ('npv', 'p5'),
    'npv_p50': ('npv', 'p50'),
    'npv_p95': ('npv', 'p95'),
    'pi_mean': ('profitability_index', 'mean'),
    'pi_p5': ('profitability_index', 'p5'),
    'pi_p50': ('profitability_index', 'p50'),
    'pi_p95': ('profitability_index', 'p95'),
}


def create_percentile_stats(mean: float, p5: float, p50: float, p95: float) -> PercentileStats:
    """Helper to create PercentileStats dict with validation."""
    return PercentileStats(mean=mean, p5=p5, p50=p50, p95=p95)


def add_backward_compat_aliases(nested_result: dict[str, Any], aliases: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Add flat key aliases to nested result for backward compatibility."""
    result = nested_result.copy()

    for flat_key, (parent_key, child_key) in aliases.items():
        if parent_key in nested_result and child_key in nested_result[parent_key]:
            result[flat_key] = nested_result[parent_key][child_key]

    return result
