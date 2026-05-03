"""
Property-based tests for ui_metrics functions using Hypothesis.

Tests mathematical properties like monotonicity, bounds checking,
and invariant preservation across realistic input ranges.
"""

import pytest
import pandas as pd
import numpy as np
import math
from hypothesis import given, strategies as st, settings, assume

import ui_metrics
import seed_registry


class TestMetricsProperties:
    """Property-based tests for metrics functions."""
    
    # Realistic strategies for financial data
    irr_strategy = st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
    coc_strategy = st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False)
    npv_strategy = st.floats(min_value=-20000000, max_value=50000000, allow_nan=False, allow_infinity=False)
    equity_multiple_strategy = st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False)
    dscr_strategy = st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False)
    ltv_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    positive_amounts = st.floats(min_value=1.0, max_value=100000000, allow_nan=False, allow_infinity=False)
    
    @given(irr_values=st.lists(irr_strategy, min_size=1, max_size=100))
    @settings(max_examples=50, deadline=None)
    def test_irr_stats_percentile_ordering(self, irr_values):
        """Property: IRR percentiles should always be ordered p5 ≤ p50 ≤ p95."""
        # Arrange
        df = pd.DataFrame({'IRR': irr_values})
        
        # Act
        result = ui_metrics.irr_stats(df)
        
        # Assert - Percentile ordering invariant
        if not math.isnan(result['p5']):
            assert result['p5'] <= result['p50']
            assert result['p50'] <= result['p95']
            assert math.isclose(result['median'], result['p50'], rel_tol=1e-9)  # Consistency check
    
    @given(irr_values=st.lists(irr_strategy, min_size=1, max_size=100))
    @settings(max_examples=50, deadline=None)
    def test_irr_stats_probability_bounds(self, irr_values):
        """Property: IRR probability >= 15% should be between 0 and 1."""
        # Arrange
        df = pd.DataFrame({'IRR': irr_values})
        
        # Act
        result = ui_metrics.irr_stats(df)
        
        # Assert - Probability bounds invariant
        if not math.isnan(result['prob_ge_15']):
            assert 0.0 <= result['prob_ge_15'] <= 1.0
    
    @given(irr_values=st.lists(irr_strategy, min_size=2, max_size=100))
    @settings(max_examples=50, deadline=None)
    def test_irr_stats_single_value_degeneracy(self, irr_values):
        """Property: When all IRR values are the same, all percentiles should equal that value."""
        # Arrange - Make all values the same
        single_value = irr_values[0]
        df = pd.DataFrame({'IRR': [single_value] * len(irr_values)})
        
        # Act
        result = ui_metrics.irr_stats(df)
        
        # Assert - All percentiles should equal the single value
        assert math.isclose(result['mean'], single_value, rel_tol=1e-6)
        assert math.isclose(result['p5'], single_value, rel_tol=1e-6)
        assert math.isclose(result['p50'], single_value, rel_tol=1e-6)
        assert math.isclose(result['p95'], single_value, rel_tol=1e-6)
    
    @given(
        coc_values=st.lists(coc_strategy, min_size=1, max_size=50),
        npv_values=st.lists(npv_strategy, min_size=1, max_size=50),
        equity_values=st.lists(positive_amounts, min_size=1, max_size=50)
    )
    @settings(max_examples=30, deadline=None)
    def test_return_value_metrics_percentile_ordering(self, coc_values, npv_values, equity_values):
        """Property: All return value metrics should have ordered percentiles."""
        # Arrange - Ensure equal lengths
        min_len = min(len(coc_values), len(npv_values), len(equity_values))
        df = pd.DataFrame({
            'CoC': coc_values[:min_len],
            'NPV': npv_values[:min_len],
            'Equity': equity_values[:min_len],
            'EquityMultiple': [1.5] * min_len  # Fixed for simplicity
        })
        
        # Act
        result = ui_metrics.return_value_metrics(df)
        
        # Assert - Percentile ordering for each metric
        for metric_name in ['coc', 'npv', 'equity_multiple', 'profitability_index']:
            metric = result[metric_name]
            if not math.isnan(metric['p5']):
                assert metric['p5'] <= metric['p50']
                assert metric['p50'] <= metric['p95']
    
    @given(
        npv_values=st.lists(npv_strategy, min_size=1, max_size=50),
        equity_values=st.lists(positive_amounts, min_size=1, max_size=50)
    )
    @settings(max_examples=30, deadline=None)
    def test_profitability_index_formula(self, npv_values, equity_values):
        """Property: Profitability Index should equal (NPV + Equity) / Equity."""
        # Arrange
        min_len = min(len(npv_values), len(equity_values))
        df = pd.DataFrame({
            'NPV': npv_values[:min_len],
            'Equity': equity_values[:min_len],
            'CoC': [0.08] * min_len,  # Fixed for simplicity
            'EquityMultiple': [1.5] * min_len
        })
        
        # Act
        result = ui_metrics.return_value_metrics(df)
        
        # Assert - PI formula should hold
        if not math.isnan(result['profitability_index']['mean']):
            expected_pi_values = [(npv + equity) / equity for npv, equity in zip(npv_values[:min_len], equity_values[:min_len])]
            expected_pi_mean = sum(expected_pi_values) / len(expected_pi_values)
            
            assert math.isclose(result['profitability_index']['mean'], expected_pi_mean, rel_tol=1e-3)
    
    @given(
        dscr_values=st.lists(dscr_strategy, min_size=1, max_size=50),
        ltv_values=st.lists(ltv_strategy, min_size=1, max_size=50)
    )
    @settings(max_examples=30, deadline=None)
    def test_risk_ops_metrics_bounds(self, dscr_values, ltv_values):
        """Property: Risk metrics should maintain reasonable bounds."""
        # Arrange
        min_len = min(len(dscr_values), len(ltv_values))
        df = pd.DataFrame({
            'DSCR': dscr_values[:min_len],
            'LTV': ltv_values[:min_len],
            'YieldOnCost': [0.06] * min_len,  # Fixed for simplicity
            'CapRate': [0.055] * min_len
        })
        
        # Act
        result = ui_metrics.risk_ops_metrics(df)
        
        # Assert - LTV should stay within reasonable bounds
        if not math.isnan(result['ltv']['mean']):
            assert 0.0 <= result['ltv']['p5'] <= 1.0
            assert 0.0 <= result['ltv']['p95'] <= 1.0
        
        # Assert - DSCR should be positive
        if not math.isnan(result['dscr']['mean']):
            assert result['dscr']['p5'] > 0.0
            assert result['dscr']['mean'] > 0.0
    
    @given(
        values=st.lists(st.floats(min_value=-100, max_value=100, allow_nan=False), min_size=1, max_size=100)
    )
    @settings(max_examples=50, deadline=None)
    def test_no_infinite_outputs(self, values):
        """Property: Metrics functions should never return infinite values (except for special cases)."""
        # Arrange
        df = pd.DataFrame({
            'IRR': values,
            'CoC': values,
            'NPV': [v * 1000000 for v in values],  # Scale for NPV
            'EquityMultiple': [abs(v) + 0.1 for v in values],  # Ensure positive
            'DSCR': [abs(v) + 0.1 for v in values],
            'LTV': [abs(v) % 1.0 for v in values],  # Keep in [0,1) range
            'YieldOnCost': [v / 100 for v in values],  # Scale for yield
            'CapRate': [v / 100 for v in values],
            'Equity': [abs(v) * 1000000 + 1000000 for v in values]  # Ensure positive, non-zero
        })
        
        # Act & Assert
        irr_result = ui_metrics.irr_stats(df)
        return_result = ui_metrics.return_value_metrics(df)
        risk_result = ui_metrics.risk_ops_metrics(df)
        
        # Check all outputs are finite or NaN (no Inf)
        for result_dict in [irr_result, return_result, risk_result]:
            for key, value in result_dict.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        assert math.isfinite(sub_value) or math.isnan(sub_value), \
                            f"Output {key}.{sub_key} should be finite or NaN, got {sub_value}"
                else:
                    assert math.isfinite(value) or math.isnan(value), \
                        f"Output {key} should be finite or NaN, got {value}"
    
    @given(n_values=st.integers(min_value=1, max_value=50))
    @settings(max_examples=20, deadline=None)
    def test_empty_dataframe_handling(self, n_values):
        """Property: Empty or missing data should be handled gracefully."""
        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        
        irr_result = ui_metrics.irr_stats(empty_df)
        return_result = ui_metrics.return_value_metrics(empty_df)
        risk_result = ui_metrics.risk_ops_metrics(empty_df)
        
        # All outputs should be NaN for empty data
        for key, value in irr_result.items():
            assert math.isnan(value), f"IRR stats {key} should be NaN for empty data"
        
        for metric_dict in [return_result, risk_result]:
            for metric_name, metric_data in metric_dict.items():
                if isinstance(metric_data, dict):
                    for stat_name, stat_value in metric_data.items():
                        assert math.isnan(stat_value), f"Metric {metric_name}.{stat_name} should be NaN for empty data"
    
    @given(
        irr_base=st.lists(irr_strategy, min_size=10, max_size=50),
        multiplier=st.floats(min_value=0.5, max_value=2.0)
    )
    @settings(max_examples=20, deadline=None)
    def test_monotonicity_scaling(self, irr_base, multiplier):
        """Property: Scaling inputs should scale outputs monotonically."""
        # Arrange
        df_base = pd.DataFrame({'IRR': irr_base})
        df_scaled = pd.DataFrame({'IRR': [x * multiplier for x in irr_base]})
        
        # Act
        result_base = ui_metrics.irr_stats(df_base)
        result_scaled = ui_metrics.irr_stats(df_scaled)
        
        # Assert - Mean should scale by the same factor (approximately)
        if not math.isnan(result_base['mean']) and not math.isnan(result_scaled['mean']):
            if result_base['mean'] != 0:  # Avoid division by zero
                scaling_factor = result_scaled['mean'] / result_base['mean']
                assert math.isclose(scaling_factor, multiplier, rel_tol=1e-3)
    
    @given(
        base_values=st.lists(st.floats(min_value=0.05, max_value=0.20), min_size=5, max_size=20),
        offset=st.floats(min_value=-0.02, max_value=0.02)
    )
    @settings(max_examples=20, deadline=None)
    def test_translation_invariance(self, base_values, offset):
        """Property: Adding constant to all values should shift percentiles by same constant."""
        # Arrange
        df_base = pd.DataFrame({'IRR': base_values})
        df_shifted = pd.DataFrame({'IRR': [x + offset for x in base_values]})
        
        # Act
        result_base = ui_metrics.irr_stats(df_base)
        result_shifted = ui_metrics.irr_stats(df_shifted)
        
        # Assert - All percentiles should shift by the offset
        if not math.isnan(result_base['mean']) and not math.isnan(result_shifted['mean']):
            for stat in ['mean', 'p5', 'p50', 'p95']:
                shift = result_shifted[stat] - result_base[stat]
                assert math.isclose(shift, offset, abs_tol=1e-6), \
                    f"Statistic {stat} should shift by {offset}, got shift of {shift}"
