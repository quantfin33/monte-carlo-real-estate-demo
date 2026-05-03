"""
Tests for irr_stats metric function.

This module tests the irr_stats function from ui_metrics.py for:
- Correctness with known inputs
- Edge case handling
- Invariant compliance
- Differential testing against reference implementation
"""

import pytest
import pandas as pd
import numpy as np
import math
from typing import Dict, Any

import ui_metrics
import seed_registry


class TestIRRStats:
    """Test suite for irr_stats metric function."""
    
    def test_irr_stats_normal_case(self):
        """Test IRR stats with normal distribution data."""
        # Arrange
        data = pd.DataFrame({
            'IRR': [0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20]
        })
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - Check structure
        assert isinstance(result, dict)
        required_keys = ['mean', 'median', 'p5', 'p50', 'p95', 'prob_ge_15']
        for key in required_keys:
            assert key in result
            assert isinstance(result[key], (int, float))
        
        # Assert - Check values with tolerance
        assert math.isclose(result['mean'], 0.14, rel_tol=1e-3)
        assert math.isclose(result['median'], 0.14, rel_tol=1e-3)
        assert math.isclose(result['p50'], 0.14, rel_tol=1e-3)
        assert result['p5'] <= result['p50'] <= result['p95']
        
        # Check probability calculation
        values_ge_15 = sum(1 for x in [0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20] if x >= 0.15)
        expected_prob = values_ge_15 / 7
        assert math.isclose(result['prob_ge_15'], expected_prob, rel_tol=1e-3)
        
    def test_irr_stats_single_value(self):
        """Test IRR stats with single value."""
        # Arrange
        data = pd.DataFrame({'IRR': [0.12]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert
        assert math.isclose(result['mean'], 0.12, rel_tol=1e-6)
        assert math.isclose(result['median'], 0.12, rel_tol=1e-6)
        assert math.isclose(result['p5'], 0.12, rel_tol=1e-6)
        assert math.isclose(result['p50'], 0.12, rel_tol=1e-6)
        assert math.isclose(result['p95'], 0.12, rel_tol=1e-6)
        assert math.isclose(result['prob_ge_15'], 0.0, rel_tol=1e-6)  # 0.12 < 0.15
        
    def test_irr_stats_empty_dataframe(self):
        """Test IRR stats with empty DataFrame."""
        # Arrange
        data = pd.DataFrame()
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - All values should be NaN
        required_keys = ['mean', 'median', 'p5', 'p50', 'p95', 'prob_ge_15']
        for key in required_keys:
            assert key in result
            assert math.isnan(result[key])
    
    def test_irr_stats_missing_column(self):
        """Test IRR stats with missing IRR column."""
        # Arrange
        data = pd.DataFrame({'OTHER': [0.1, 0.2, 0.3]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - All values should be NaN
        required_keys = ['mean', 'median', 'p5', 'p50', 'p95', 'prob_ge_15']
        for key in required_keys:
            assert key in result
            assert math.isnan(result[key])
    
    def test_irr_stats_all_nan_values(self):
        """Test IRR stats with all NaN IRR values."""
        # Arrange
        data = pd.DataFrame({'IRR': [np.nan, np.nan, np.nan]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - All values should be NaN
        required_keys = ['mean', 'median', 'p5', 'p50', 'p95', 'prob_ge_15']
        for key in required_keys:
            assert key in result
            assert math.isnan(result[key])
    
    def test_irr_stats_mixed_valid_nan(self):
        """Test IRR stats with mix of valid and NaN values."""
        # Arrange
        data = pd.DataFrame({'IRR': [0.10, np.nan, 0.14, np.nan, 0.18]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - Should calculate on valid values only
        assert math.isclose(result['mean'], 0.14, rel_tol=1e-3)  # (0.10 + 0.14 + 0.18) / 3
        assert math.isclose(result['median'], 0.14, rel_tol=1e-3)
        assert result['p5'] <= result['p50'] <= result['p95']
        
        # 1 out of 3 valid values >= 0.15
        assert math.isclose(result['prob_ge_15'], 1/3, rel_tol=1e-3)
    
    def test_irr_stats_extreme_values(self):
        """Test IRR stats with extreme values."""
        # Arrange
        data = pd.DataFrame({'IRR': [-0.5, -0.1, 0.0, 0.5, 1.0]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - Should handle without error
        assert isinstance(result['mean'], float)
        assert not math.isnan(result['mean'])
        assert result['p5'] <= result['p50'] <= result['p95']
        assert 0.0 <= result['prob_ge_15'] <= 1.0
    
    def test_irr_stats_invariants(self):
        """Test that IRR stats satisfy mathematical invariants."""
        # Arrange
        np.random.seed(seed_registry.get_test_seed('invariant'))
        data = pd.DataFrame({'IRR': np.random.normal(0.12, 0.05, 1000)})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - Invariant: percentile ordering
        assert result['p5'] <= result['p50']
        assert result['p50'] <= result['p95']
        
        # Assert - Invariant: median == p50
        assert math.isclose(result['median'], result['p50'], rel_tol=1e-6)
        
        # Assert - Invariant: probability range
        assert 0.0 <= result['prob_ge_15'] <= 1.0
        
        # Assert - Invariant: all values are finite or NaN
        for key, value in result.items():
            assert math.isfinite(value) or math.isnan(value)
            assert not math.isinf(value)
    
    def test_irr_stats_differential_reference(self):
        """Differential test against simple reference implementation."""
        # Arrange
        test_data = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.22]
        data = pd.DataFrame({'IRR': test_data})
        
        # Reference implementation
        def reference_irr_stats(irr_values):
            if not irr_values:
                return {k: float('nan') for k in ['mean', 'median', 'p5', 'p50', 'p95', 'prob_ge_15']}
            
            values = sorted(irr_values)
            n = len(values)
            
            return {
                'mean': sum(values) / n,
                'median': values[n//2] if n % 2 == 1 else (values[n//2-1] + values[n//2]) / 2,
                'p5': np.percentile(values, 5),
                'p50': np.percentile(values, 50),
                'p95': np.percentile(values, 95),
                'prob_ge_15': sum(1 for x in values if x >= 0.15) / n
            }
        
        # Act
        result = ui_metrics.irr_stats(data)
        reference = reference_irr_stats(test_data)
        
        # Assert - Compare with reference (allowing small numerical differences)
        for key in reference.keys():
            if math.isnan(reference[key]):
                assert math.isnan(result[key])
            else:
                assert math.isclose(result[key], reference[key], rel_tol=1e-3)
    
    def test_irr_stats_type_safety(self):
        """Test that all outputs are proper Python floats."""
        # Arrange
        data = pd.DataFrame({'IRR': [0.10, 0.12, 0.14]})
        
        # Act
        result = ui_metrics.irr_stats(data)
        
        # Assert - Type safety
        for key, value in result.items():
            assert isinstance(value, float), f"Key {key} should be float, got {type(value)}"
    
    @pytest.mark.performance
    def test_irr_stats_performance(self):
        """Test performance with large dataset."""
        # Arrange
        np.random.seed(seed_registry.get_test_seed('performance'))
        large_data = pd.DataFrame({'IRR': np.random.normal(0.12, 0.05, 10000)})
        
        # Act & Assert - Should complete without performance issues
        result = ui_metrics.irr_stats(large_data)
        
        # Basic validation
        assert isinstance(result, dict)
        assert not math.isnan(result['mean'])
        assert result['p5'] <= result['p50'] <= result['p95']
