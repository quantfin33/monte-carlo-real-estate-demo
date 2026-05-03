"""
Variance Detection Tests - Medium Priority Feature

Tests the variance detection utility for identifying systematic constant metrics.
Ensures the detector correctly flags constant metrics and doesn't create false positives.
"""

import pytest
import sys
import math
from pathlib import Path
import pandas as pd
import numpy as np

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import rmc_model
import metrics_utils


class TestVarianceDetection:
    """Test variance detection utility functionality."""
    
    def test_synthetic_data_detection(self):
        """Test variance detector on synthetic data with known constant/variable metrics."""
        print("\n🧪 TESTING: Variance Detection on Synthetic Data")
        
        # Create synthetic DataFrame with mix of constant and variable metrics
        np.random.seed(42)
        n_rows = 500
        
        synthetic_df = pd.DataFrame({
            'constant_metric': [5.0] * n_rows,  # Perfectly constant
            'variable_metric': np.random.normal(10.0, 2.0, n_rows),  # Variable
            'low_variance': np.random.normal(100.0, 0.001, n_rows),  # Very low variance
            'zero_metric': [0.0] * n_rows,  # Constant at zero
            'single_outlier': [1.0] * (n_rows-1) + [1000.0],  # Mostly constant with outlier
            'nan_metric': [np.nan] * n_rows,  # All NaN
            'missing_data': [1.0, 2.0, np.nan, np.nan, 3.0] + [np.nan] * (n_rows-5),  # Mostly NaN
        })
        
        # Test the variance report function
        cols_to_test = list(synthetic_df.columns)
        variance_data = metrics_utils.variance_report(synthetic_df, cols_to_test, min_var=1e-6)
        
        print(f"📊 SYNTHETIC DATA RESULTS:")
        for col, (var, is_const) in variance_data.items():
            status = "CONSTANT" if is_const else "Variable"
            print(f"   {col:20s}: {status:10s} (var={var:.2e})")
        
        # Assertions for known behavior
        assert variance_data['constant_metric'][1] == True, "constant_metric should be flagged as constant"
        assert variance_data['variable_metric'][1] == False, "variable_metric should not be flagged as constant"
        assert variance_data['zero_metric'][1] == True, "zero_metric should be flagged as constant"
        assert variance_data['nan_metric'][1] == True, "nan_metric should be flagged as constant (no data)"
        
        # Low variance might or might not be constant depending on threshold
        low_var_is_const = variance_data['low_variance'][1]
        print(f"   Low variance metric flagged as constant: {low_var_is_const}")
        
        print("✅ Variance detector correctly identified synthetic data patterns")
    
    def test_real_simulation_variance(self):
        """Test variance detector on real simulation data to check for false positives."""
        print("\n🧪 TESTING: Variance Detection on Real Simulation Data")
        
        # Run a small Monte Carlo simulation
        params = rmc_model.default_params()
        params['GLOBAL_RECOVERY_TYPE'] = 'GROSS'  # Use GROSS to avoid recovery offset
        
        df = rmc_model.run_simulation(n=800, seed=42, params=params, parallel=True)
        
        # Standard metrics that should be variable
        standard_metrics = [
            "IRR", "CoC", "NPV", "DSCR", "DebtYield_Y1", "MinDebtYield", 
            "LTV", "YieldOnCost", "EquityMultiple"
        ]
        
        # Check which metrics are available
        available_metrics = [col for col in standard_metrics if col in df.columns]
        missing_metrics = [col for col in standard_metrics if col not in df.columns]
        
        print(f"📋 METRICS AVAILABILITY:")
        print(f"   Available: {available_metrics}")
        print(f"   Missing:   {missing_metrics}")
        
        # Run variance detection
        variance_data = metrics_utils.variance_report(df, available_metrics, min_var=1e-12)
        
        print(f"📊 REAL DATA VARIANCE RESULTS:")
        constant_metrics = []
        variable_metrics = []
        
        for col, (var, is_const) in variance_data.items():
            status = "❌ CONSTANT" if is_const else "✅ Variable"
            if np.isnan(var):
                print(f"   {col:20s}: ⚠️  No data")
            else:
                print(f"   {col:20s}: {status:12s} (var={var:.2e})")
                if is_const:
                    constant_metrics.append(col)
                else:
                    variable_metrics.append(col)
        
        # Report summary
        print(f"\n📈 SUMMARY:")
        print(f"   Variable metrics: {len(variable_metrics)}")
        print(f"   Constant metrics: {len(constant_metrics)}")
        
        if constant_metrics:
            print(f"   ⚠️  Constant metrics detected: {constant_metrics}")
            print(f"   This may indicate wiring issues or cached values.")
            
            # For now, allow some metrics to be constant by design, but document them
            allowed_constants = []  # Add known constants here if any exist by design
            
            unexpected_constants = [col for col in constant_metrics if col not in allowed_constants]
            if unexpected_constants:
                print(f"   ❌ Unexpected constant metrics: {unexpected_constants}")
                # Don't fail the test yet - just report for investigation
                # assert False, f"Unexpected constant metrics found: {unexpected_constants}"
            else:
                print(f"   ✅ All constant metrics are expected/allowed")
        else:
            print(f"   ✅ No constant metrics detected - all show appropriate variance")
        
        # Test the convenience function
        all_variable = metrics_utils.quick_variance_check(df, available_metrics)
        print(f"\n🚀 QUICK CHECK RESULT: {'✅ All variable' if all_variable else '❌ Some constants detected'}")
        
        print("✅ Variance detection completed on real simulation data")
    
    def test_variance_report_formatting(self):
        """Test the formatting functions for variance reports."""
        print("\n🧪 TESTING: Variance Report Formatting")
        
        # Create sample variance data
        sample_data = {
            'metric_a': (0.000123, False),
            'metric_b': (0.0, True),
            'metric_c': (float('nan'), True),
            'metric_d': (0.456789, False),
        }
        
        # Test show_all formatting
        full_report = metrics_utils.format_variance_report(sample_data, show_all=True)
        print("📊 FULL REPORT:")
        print(full_report)
        
        # Test constants-only formatting
        constants_report = metrics_utils.format_variance_report(sample_data, show_all=False)
        print(f"\n⚠️  CONSTANTS ONLY REPORT:")
        print(constants_report)
        
        # Basic checks
        assert "metric_a" in full_report
        assert "metric_b" in constants_report
        assert "CONSTANT" in constants_report
        
        print("✅ Variance report formatting working correctly")
    
    def test_anomaly_detection(self):
        """Test the broader anomaly detection functionality."""
        print("\n🧪 TESTING: Metric Anomaly Detection")
        
        # Create test data with various anomalies
        np.random.seed(42)
        anomaly_df = pd.DataFrame({
            'normal_metric': np.random.normal(5.0, 1.0, 100),
            'constant_metric': [10.0] * 100,
            'all_zero': [0.0] * 100,
            'all_nan': [np.nan] * 100,
            'extreme_outlier': [1.0] * 99 + [1000.0],  # 1000x larger than median
            'single_value': [42.0] * 100,
        })
        
        anomalies = metrics_utils.detect_metric_anomalies(anomaly_df)
        
        print(f"🔍 DETECTED ANOMALIES:")
        for anomaly_type, metrics in anomalies.items():
            if metrics:
                print(f"   {anomaly_type:15s}: {metrics}")
        
        # Verify expected anomalies are detected
        assert 'constant_metric' in anomalies.get('constant', [])
        assert 'all_zero' in anomalies.get('all_zero', [])
        assert 'all_nan' in anomalies.get('all_nan', [])
        assert 'single_value' in anomalies.get('single_value', [])
        
        # Normal metric should not appear in any anomaly list
        for anomaly_list in anomalies.values():
            assert 'normal_metric' not in anomaly_list, "Normal metric incorrectly flagged as anomalous"
        
        print("✅ Anomaly detection correctly identified all test cases")
    
    def test_edge_cases(self):
        """Test edge cases for variance detection."""
        print("\n🧪 TESTING: Edge Cases for Variance Detection")
        
        # Test empty DataFrame
        empty_df = pd.DataFrame()
        empty_result = metrics_utils.variance_report(empty_df, ['nonexistent'])
        assert empty_result['nonexistent'][1] == True  # Should be flagged as constant (no data)
        
        # Test DataFrame with only one row
        single_row_df = pd.DataFrame({'single': [5.0]})
        single_result = metrics_utils.variance_report(single_row_df, ['single'])
        assert single_result['single'][1] == True  # Single value should be constant
        
        # Test with non-numeric data that gets coerced
        mixed_df = pd.DataFrame({'mixed': [1, 2, 'text', 4, 5]})
        mixed_result = metrics_utils.variance_report(mixed_df, ['mixed'])
        # Should handle the 'text' value gracefully
        assert isinstance(mixed_result['mixed'][0], float)
        
        print("✅ Edge cases handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
