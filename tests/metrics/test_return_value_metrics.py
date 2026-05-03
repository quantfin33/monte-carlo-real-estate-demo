"""
Tests for return_value_metrics function.

This module tests the return_value_metrics function from ui_metrics.py for:
- Correctness with known inputs
- Edge case handling (missing columns, NaN values)
- Profitability Index calculation logic
- Type safety and error handling
"""

import pytest
import pandas as pd
import numpy as np
import math
from typing import Dict, Any

import ui_metrics
import seed_registry


class TestReturnValueMetrics:
    """Test suite for return_value_metrics function."""
    
    def test_return_value_metrics_complete_data(self):
        """Test return value metrics with all required columns."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.06, 0.08, 0.10, 0.12, 0.14],
            'EquityMultiple': [1.5, 1.6, 1.7, 1.8, 1.9],
            'NPV': [1000000, 2000000, 3000000, 4000000, 5000000],
            'Equity': [10000000, 10000000, 10000000, 10000000, 10000000]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Structure
        assert isinstance(result, dict)
        expected_metrics = ['coc', 'equity_multiple', 'npv', 'profitability_index']
        for metric in expected_metrics:
            assert metric in result
            assert isinstance(result[metric], dict)
            
            # Each metric should have percentile stats
            for stat in ['p5', 'p50', 'p95', 'mean']:
                assert stat in result[metric]
                assert isinstance(result[metric][stat], (int, float))
        
        # Assert - CoC values
        assert math.isclose(result['coc']['mean'], 0.10, rel_tol=1e-3)
        assert math.isclose(result['coc']['p50'], 0.10, rel_tol=1e-3)
        assert result['coc']['p5'] <= result['coc']['p50'] <= result['coc']['p95']
        
        # Assert - Equity Multiple values
        assert math.isclose(result['equity_multiple']['mean'], 1.7, rel_tol=1e-3)
        assert math.isclose(result['equity_multiple']['p50'], 1.7, rel_tol=1e-3)
        
        # Assert - NPV values
        assert math.isclose(result['npv']['mean'], 3000000.0, rel_tol=1e-3)
        assert math.isclose(result['npv']['p50'], 3000000.0, rel_tol=1e-3)
        
        # Assert - Profitability Index logic: PI = (NPV + Equity) / Equity
        expected_pi_mean = (3000000 + 10000000) / 10000000  # 1.3
        assert math.isclose(result['profitability_index']['mean'], expected_pi_mean, rel_tol=1e-3)
    
    def test_return_value_metrics_missing_equity(self):
        """Test return value metrics without Equity column."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.08, 0.10, 0.12],
            'EquityMultiple': [1.6, 1.7, 1.8],
            'NPV': [2000000, 3000000, 4000000]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Basic metrics should work
        assert math.isclose(result['coc']['mean'], 0.10, rel_tol=1e-3)
        assert math.isclose(result['equity_multiple']['mean'], 1.7, rel_tol=1e-3)
        assert math.isclose(result['npv']['mean'], 3000000.0, rel_tol=1e-3)
        
        # Assert - Profitability Index should be NaN
        assert math.isnan(result['profitability_index']['mean'])
        assert math.isnan(result['profitability_index']['p5'])
        assert math.isnan(result['profitability_index']['p50'])
        assert math.isnan(result['profitability_index']['p95'])
    
    def test_return_value_metrics_missing_columns(self):
        """Test return value metrics with missing required columns."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.08, 0.10, 0.12],
            'SomeOtherColumn': [1, 2, 3]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Available metric should work
        assert math.isclose(result['coc']['mean'], 0.10, rel_tol=1e-3)
        
        # Assert - Missing metrics should be NaN
        assert math.isnan(result['equity_multiple']['mean'])
        assert math.isnan(result['npv']['mean'])
        assert math.isnan(result['profitability_index']['mean'])
    
    def test_return_value_metrics_nan_values(self):
        """Test return value metrics with NaN values."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.08, np.nan, 0.12, np.nan, 0.16],
            'EquityMultiple': [1.6, 1.7, np.nan, 1.9, np.nan],
            'NPV': [2000000, np.nan, 4000000, np.nan, 6000000],
            'Equity': [10000000, 10000000, 10000000, 10000000, 10000000]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Should calculate on valid values only
        # CoC: valid values are [0.08, 0.12, 0.16], mean = 0.12
        assert math.isclose(result['coc']['mean'], 0.12, rel_tol=1e-3)
        
        # EquityMultiple: valid values are [1.6, 1.7, 1.9], mean = 1.733...
        assert math.isclose(result['equity_multiple']['mean'], 1.7333, rel_tol=1e-2)
        
        # NPV: valid values are [2M, 4M, 6M], mean = 4M
        assert math.isclose(result['npv']['mean'], 4000000.0, rel_tol=1e-3)
    
    def test_return_value_metrics_negative_npv(self):
        """Test return value metrics with negative NPV values."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.05, 0.07, 0.09],
            'EquityMultiple': [0.8, 0.9, 1.1],  # Some below 1.0
            'NPV': [-1000000, 0, 1000000],      # Mix of negative, zero, positive
            'Equity': [10000000, 10000000, 10000000]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Should handle negative NPV normally
        assert math.isclose(result['npv']['mean'], 0.0, abs_tol=1e-3)
        
        # Assert - Profitability Index with negative NPV
        # PI = (NPV + Equity) / Equity = (0 + 10M) / 10M = 1.0
        assert math.isclose(result['profitability_index']['mean'], 1.0, rel_tol=1e-3)
    
    def test_return_value_metrics_zero_equity(self):
        """Test return value metrics with zero equity (edge case)."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.08, 0.10, 0.12],
            'EquityMultiple': [1.6, 1.7, 1.8],
            'NPV': [2000000, 3000000, 4000000],
            'Equity': [0, 0, 0]  # Zero equity
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Basic metrics should work
        assert math.isclose(result['coc']['mean'], 0.10, rel_tol=1e-3)
        assert math.isclose(result['npv']['mean'], 3000000.0, rel_tol=1e-3)
        
        # Assert - Profitability Index should be NaN (NPV/0 -> Inf -> NaN for safety)
        assert math.isnan(result['profitability_index']['mean'])
    
    def test_return_value_metrics_invariants(self):
        """Test that return value metrics satisfy mathematical invariants."""
        # Arrange
        np.random.seed(seed_registry.get_test_seed('invariant'))
        data = pd.DataFrame({
            'CoC': np.random.normal(0.08, 0.02, 100),
            'EquityMultiple': np.random.normal(1.7, 0.3, 100),
            'NPV': np.random.normal(3000000, 1000000, 100),
            'Equity': np.full(100, 10000000)
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Percentile ordering for each metric
        for metric_name in ['coc', 'equity_multiple', 'npv', 'profitability_index']:
            metric = result[metric_name]
            if not math.isnan(metric['p5']):  # Skip if all NaN
                assert metric['p5'] <= metric['p50']
                assert metric['p50'] <= metric['p95']
        
        # Assert - Profitability Index relationship: PI = NPV/Equity + 1
        if not math.isnan(result['profitability_index']['mean']):
            expected_pi = result['npv']['mean'] / 10000000 + 1
            assert math.isclose(result['profitability_index']['mean'], expected_pi, rel_tol=1e-3)
    
    def test_return_value_metrics_type_safety(self):
        """Test that all outputs are proper Python floats."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.08, 0.10, 0.12],
            'EquityMultiple': [1.6, 1.7, 1.8],
            'NPV': [2000000, 3000000, 4000000]
        })
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - Type safety for canonical nested keys
        canonical_metrics = ['coc', 'equity_multiple', 'npv', 'profitability_index']
        for metric_name in canonical_metrics:
            assert metric_name in result
            metric_data = result[metric_name]
            assert isinstance(metric_data, dict), f"Canonical metric {metric_name} should be dict"
            for stat_name, stat_value in metric_data.items():
                assert isinstance(stat_value, float), f"Metric {metric_name}.{stat_name} should be float, got {type(stat_value)}"
        
        # Assert - Backward compatibility flat keys are also floats
        flat_keys = ['coc_mean', 'coc_p5', 'npv_mean', 'pi_mean']
        for flat_key in flat_keys:
            if flat_key in result:
                assert isinstance(result[flat_key], float), f"Flat key {flat_key} should be float"
    
    def test_return_value_metrics_empty_dataframe(self):
        """Test return value metrics with empty DataFrame."""
        # Arrange
        data = pd.DataFrame()
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Assert - All metrics should have NaN values
        expected_metrics = ['coc', 'equity_multiple', 'npv', 'profitability_index']
        for metric in expected_metrics:
            assert metric in result
            for stat in ['p5', 'p50', 'p95', 'mean']:
                assert math.isnan(result[metric][stat])
    
    def test_return_value_metrics_differential_reference(self):
        """Differential test against simple reference implementation."""
        # Arrange
        data = pd.DataFrame({
            'CoC': [0.06, 0.08, 0.10],
            'EquityMultiple': [1.5, 1.7, 1.9],
            'NPV': [1000000, 3000000, 5000000],
            'Equity': [10000000, 10000000, 10000000]
        })
        
        # Reference implementation
        def reference_percentiles(values):
            if not values or all(math.isnan(x) for x in values):
                return {'mean': float('nan'), 'p5': float('nan'), 'p50': float('nan'), 'p95': float('nan')}
            
            clean_values = [x for x in values if not math.isnan(x)]
            if not clean_values:
                return {'mean': float('nan'), 'p5': float('nan'), 'p50': float('nan'), 'p95': float('nan')}
            
            return {
                'mean': sum(clean_values) / len(clean_values),
                'p5': np.percentile(clean_values, 5),
                'p50': np.percentile(clean_values, 50),
                'p95': np.percentile(clean_values, 95)
            }
        
        # Act
        result = ui_metrics.return_value_metrics(data)
        
        # Reference calculations
        ref_coc = reference_percentiles([0.06, 0.08, 0.10])
        ref_pi = reference_percentiles([(1000000 + 10000000) / 10000000, 
                                      (3000000 + 10000000) / 10000000,
                                      (5000000 + 10000000) / 10000000])
        
        # Assert - Compare with reference
        for stat in ['mean', 'p5', 'p50', 'p95']:
            assert math.isclose(result['coc'][stat], ref_coc[stat], rel_tol=1e-3)
            assert math.isclose(result['profitability_index'][stat], ref_pi[stat], rel_tol=1e-3)
