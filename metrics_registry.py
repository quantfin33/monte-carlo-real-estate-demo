"""
Metrics Registry - Central registry of all available metrics.

This module provides a centralized registry of all metrics available in ui_metrics.py,
along with their metadata for testing and validation purposes.
"""

from typing import Dict, List, Any, Callable
from dataclasses import dataclass
import ui_metrics


@dataclass
class MetricDefinition:
    """Definition of a metric including its properties and validation info."""
    name: str
    function: Callable
    description: str
    output_type: str  # 'dict' or 'float'
    dependencies: List[str]  # Required DataFrame columns
    invariants: List[str]  # Human-readable invariants


# Registry of all metrics with their definitions
METRICS_REGISTRY: Dict[str, MetricDefinition] = {
    'irr_stats': MetricDefinition(
        name='irr_stats',
        function=ui_metrics.irr_stats,
        description='Internal Rate of Return statistics (mean, median, percentiles)',
        output_type='dict',
        dependencies=['IRR'],
        invariants=[
            'IRR values should be finite numbers',
            'Percentiles should be ordered: p5 <= p50 <= p95',
            'prob_ge_15 should be between 0 and 1'
        ]
    ),
    'capex_adj_irr_mean': MetricDefinition(
        name='capex_adj_irr_mean',
        function=ui_metrics.capex_adj_irr_mean,
        description='Mean CapEx-adjusted IRR',
        output_type='float',
        dependencies=['IRR_CapEx_Adj'],
        invariants=[
            'Should be a finite number',
            'Typically between -50% and +50% for real estate'
        ]
    ),
    'return_value_metrics': MetricDefinition(
        name='return_value_metrics',
        function=ui_metrics.return_value_metrics,
        description='Return and value metrics: CoC, Equity Multiple, NPV, PI',
        output_type='dict',
        dependencies=['CoC', 'EquityMultiple', 'NPV'],
        invariants=[
            'CoC should be finite',
            'EquityMultiple should be positive for successful investments',
            'NPV can be negative or positive',
            'Percentiles should be ordered'
        ]
    ),
    'risk_ops_metrics': MetricDefinition(
        name='risk_ops_metrics',
        function=ui_metrics.risk_ops_metrics,
        description='Risk and operations metrics: YoC, CapRate, LTV, DSCR',
        output_type='dict',
        dependencies=['YieldOnCost', 'CapRate', 'LTV', 'DSCR'],
        invariants=[
            'YoC should be positive',
            'CapRate should be between 0% and 20% typically',
            'LTV should be between 0% and 100%',
            'DSCR should be positive, typically > 1.0'
        ]
    ),
    'covenant_minima': MetricDefinition(
        name='covenant_minima',
        function=ui_metrics.covenant_minima,
        description='Minimum covenant metrics over the holding period',
        output_type='dict',
        dependencies=['MinDSCR', 'MinDebtYield'],
        invariants=[
            'MinDSCR should be positive',
            'MinDebtYield should be positive',
            'Both should be finite numbers'
        ]
    ),
    'operational_risk_metrics': MetricDefinition(
        name='operational_risk_metrics',
        function=ui_metrics.operational_risk_metrics,
        description='Operational and risk metrics: GOI, Revenue Growth, Occupancy',
        output_type='dict',
        dependencies=['GrossOperatingIncome', 'RevenueGrowthYoY', 'OccupancyRate'],
        invariants=[
            'GOI should be positive',
            'Revenue growth can be positive or negative',
            'Occupancy rate should be between 0% and 100%'
        ]
    ),
    'advanced_financial_metrics': MetricDefinition(
        name='advanced_financial_metrics',
        function=ui_metrics.advanced_financial_metrics,
        description='Advanced financial metrics: FFO, AFFO, NAV',
        output_type='dict',
        dependencies=['FFO', 'AFFO', 'NAV'],
        invariants=[
            'FFO can be positive or negative',
            'AFFO typically lower than FFO',
            'NAV should be finite'
        ]
    ),
    'financial_ratios_metrics': MetricDefinition(
        name='financial_ratios_metrics',
        function=ui_metrics.financial_ratios_metrics,
        description='Financial ratios: PI, Net Cash Flow, Price-to-Rent, etc.',
        output_type='dict',
        dependencies=['NPV', 'Equity', 'PurchasePrice'],
        invariants=[
            'Profitability Index should be positive',
            'Price-to-Rent ratio should be positive',
            'Debt-to-Equity ratio should be positive'
        ]
    ),
    'fifty_percent_rule_metrics': MetricDefinition(
        name='fifty_percent_rule_metrics',
        function=ui_metrics.fifty_percent_rule_metrics,
        description='50% Rule calculations for real estate analysis',
        output_type='dict',
        dependencies=['FiftyPercentRuleRatio', 'FiftyPercentRulePass'],
        invariants=[
            'Rule ratio should be positive',
            'Rule pass should be boolean-like (0 or 1)',
            'Expenses should be positive'
        ]
    ),
    'reit_investment_metrics': MetricDefinition(
        name='reit_investment_metrics',
        function=ui_metrics.reit_investment_metrics,
        description='REIT and investment analysis metrics',
        output_type='dict',
        dependencies=['FFO_PayoutRatio', 'ReturnOnCost', 'InvestmentRating'],
        invariants=[
            'Payout ratio should be positive',
            'Return on Cost should be positive',
            'Investment rating should be between 0 and 100'
        ]
    )
}


def get_all_metrics() -> List[str]:
    """Get list of all available metric names."""
    return list(METRICS_REGISTRY.keys())


def get_metric_dependencies() -> Dict[str, List[str]]:
    """Get mapping of metric names to their required DataFrame columns."""
    return {name: defn.dependencies for name, defn in METRICS_REGISTRY.items()}


def get_metric_invariants() -> Dict[str, List[str]]:
    """Get mapping of metric names to their invariants."""
    return {name: defn.invariants for name, defn in METRICS_REGISTRY.items()}


def validate_metric_output(metric_name: str, output: Any) -> bool:
    """Validate that metric output conforms to expected type and basic constraints."""
    if metric_name not in METRICS_REGISTRY:
        return False
    
    defn = METRICS_REGISTRY[metric_name]
    
    if defn.output_type == 'dict':
        return isinstance(output, dict)
    elif defn.output_type == 'float':
        return isinstance(output, (int, float)) and not (output != output)  # Check for NaN
    
    return False
