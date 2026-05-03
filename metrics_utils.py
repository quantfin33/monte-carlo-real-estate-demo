"""
Metrics Utilities for Real Estate Monte Carlo Model

Provides helper functions for detecting systematic constant metrics
and other metric validation utilities.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List


def variance_report(df: pd.DataFrame, cols: List[str], min_var: float = 1e-12) -> Dict[str, Tuple[float, bool]]:
    """
    Returns {col: (variance, is_constant)} where is_constant=True if var < min_var or df[col].nunique() == 1.
    Ignores NaNs and coerces to float.
    
    Args:
        df: DataFrame containing metrics data
        cols: List of column names to analyze
        min_var: Minimum variance threshold below which metrics are considered constant
        
    Returns:
        Dictionary mapping column names to (variance, is_constant) tuples
        
    Example:
        >>> df = pd.DataFrame({'metric_a': [1, 2, 3], 'metric_b': [5, 5, 5]})
        >>> variance_report(df, ['metric_a', 'metric_b'])
        {'metric_a': (0.6666666666666666, False), 'metric_b': (0.0, True)}
    """
    out = {}
    for c in cols:
        if c not in df.columns:
            out[c] = (float('nan'), True)
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            out[c] = (float('nan'), True)
            continue
        v = float(np.var(s))
        is_const = (v < min_var) or (s.nunique() == 1)
        out[c] = (v, is_const)
    return out


def format_variance_report(variance_data: Dict[str, Tuple[float, bool]], 
                          show_all: bool = False) -> str:
    """
    Format variance report data into a readable string.
    
    Args:
        variance_data: Output from variance_report()
        show_all: If True, show all metrics. If False, only show constant ones.
        
    Returns:
        Formatted string report
    """
    lines = []
    
    if show_all:
        lines.append("📊 VARIANCE REPORT (All Metrics)")
        lines.append("=" * 50)
        
        for col, (var, is_const) in sorted(variance_data.items()):
            status = "❌ CONSTANT" if is_const else "✅ Variable"
            if np.isnan(var):
                lines.append(f"  {col:20s}: {status:12s} (No data)")
            else:
                lines.append(f"  {col:20s}: {status:12s} (var={var:.2e})")
    else:
        # Only show constant metrics
        constant_metrics = [(col, var, is_const) for col, (var, is_const) in variance_data.items() if is_const]
        
        if constant_metrics:
            lines.append("⚠️  CONSTANT METRICS DETECTED")
            lines.append("=" * 40)
            
            for col, var, is_const in sorted(constant_metrics):
                if np.isnan(var):
                    lines.append(f"  {col:20s}: No data")
                else:
                    lines.append(f"  {col:20s}: var={var:.2e}")
                    
            lines.append("")
            lines.append("These metrics show no variance across simulation runs.")
            lines.append("This may indicate wiring issues or cached values.")
        else:
            lines.append("✅ No constant metrics detected - all metrics show appropriate variance.")
    
    return "\n".join(lines)


def quick_variance_check(df: pd.DataFrame, 
                        standard_metrics: List[str] = None,
                        min_var: float = 1e-12) -> bool:
    """
    Quick check to see if any standard metrics are constant.
    
    Args:
        df: DataFrame containing simulation results
        standard_metrics: List of metrics to check (uses defaults if None)
        min_var: Minimum variance threshold
        
    Returns:
        True if all metrics are variable, False if any are constant
    """
    if standard_metrics is None:
        standard_metrics = [
            "IRR", "CoC", "NPV", "DSCR", "DebtYield_Y1", "MinDebtYield", 
            "LTV", "YieldOnCost", "EquityMultiple"
        ]
    
    variance_data = variance_report(df, standard_metrics, min_var)
    constant_count = sum(1 for _, (_, is_const) in variance_data.items() if is_const)
    
    return constant_count == 0


def detect_metric_anomalies(df: pd.DataFrame, 
                          metrics: List[str] = None) -> Dict[str, List[str]]:
    """
    Detect common metric anomalies beyond just constant values.
    
    Args:
        df: DataFrame containing simulation results
        metrics: List of metrics to analyze (auto-detect if None)
        
    Returns:
        Dictionary of anomaly_type -> [list of affected metrics]
    """
    if metrics is None:
        # Auto-detect numeric columns that look like metrics
        metrics = [col for col in df.columns 
                  if df[col].dtype in ['float64', 'int64'] and not col.startswith('_')]
    
    anomalies = {
        'constant': [],
        'all_nan': [],
        'all_zero': [],
        'extreme_outliers': [],
        'single_value': []
    }
    
    for col in metrics:
        if col not in df.columns:
            continue
            
        s = pd.to_numeric(df[col], errors="coerce")
        s_clean = s.dropna()
        
        # Check for all NaN
        if s_clean.empty:
            anomalies['all_nan'].append(col)
            continue
            
        # Check for constant (zero variance)
        if s_clean.var() < 1e-12:
            anomalies['constant'].append(col)
            
        # Check for all zero
        if (s_clean == 0).all():
            anomalies['all_zero'].append(col)
            
        # Check for single unique value
        if s_clean.nunique() == 1:
            anomalies['single_value'].append(col)
            
        # Check for extreme outliers (values > 100x the median)
        if len(s_clean) > 10:  # Only check if we have enough data
            median_val = s_clean.median()
            if median_val != 0:
                outlier_threshold = abs(median_val) * 100
                outliers = s_clean[abs(s_clean) > outlier_threshold]
                if len(outliers) > 0:
                    anomalies['extreme_outliers'].append(col)
    
    # Remove empty lists
    return {k: v for k, v in anomalies.items() if v}
