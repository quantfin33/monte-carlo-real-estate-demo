"""
Wiring tests - verify UI integration and column coverage.

Tests include:
- UI can import and use ui_metrics.py functions without errors
- Column coverage tests verify required columns exist or are handled gracefully
- End-to-end functionality without Streamlit context
- Function availability and interface compliance

These tests ensure the integration between ui_metrics.py and the UI works correctly.
"""

import pytest
import importlib
import inspect
import pandas as pd
import ui_metrics


class TestUIMetricsImport:
    """Test that ui_metrics.py can be imported and used."""
    
    def test_ui_metrics_imports_successfully(self):
        """Test that ui_metrics module imports without errors."""
        # Reimport to ensure clean state
        importlib.reload(ui_metrics)
        
        # Should not raise any exceptions
        assert hasattr(ui_metrics, 'irr_stats')
        assert hasattr(ui_metrics, 'return_value_metrics')
        assert hasattr(ui_metrics, 'risk_ops_metrics')
    
    def test_all_required_functions_exist(self):
        """Test that all required metric functions exist in ui_metrics."""
        required_functions = [
            'irr_stats',
            'capex_adj_irr_mean',
            'return_value_metrics',
            'risk_ops_metrics',
            'covenant_minima',
            'prepay_defeasance',
            'operational_risk_metrics',
            'advanced_financial_metrics',
            'financial_ratios_metrics',
            'fifty_percent_rule_metrics',
            'reit_investment_metrics',
            'additional_kpis'
        ]
        
        for func_name in required_functions:
            assert hasattr(ui_metrics, func_name), f"Missing required function: {func_name}"
            assert callable(getattr(ui_metrics, func_name)), f"Function {func_name} is not callable"
    
    def test_function_signatures_accept_dataframe(self):
        """Test that all metric functions accept DataFrame as first parameter."""
        metric_functions = [
            ui_metrics.irr_stats,
            ui_metrics.capex_adj_irr_mean,
            ui_metrics.return_value_metrics,
            ui_metrics.risk_ops_metrics,
            ui_metrics.covenant_minima,
            ui_metrics.prepay_defeasance,
            ui_metrics.operational_risk_metrics,
            ui_metrics.advanced_financial_metrics,
            ui_metrics.financial_ratios_metrics,
            ui_metrics.fifty_percent_rule_metrics,
            ui_metrics.reit_investment_metrics,
            ui_metrics.additional_kpis
        ]
        
        for func in metric_functions:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            # First parameter should be DataFrame-like
            assert len(params) >= 1, f"Function {func.__name__} has no parameters"
            first_param = params[0]
            
            # Common DataFrame parameter names
            valid_names = ['df', 'data', 'dataframe', 'simulation_results']
            assert first_param in valid_names or 'df' in first_param.lower(), \
                f"Function {func.__name__} first parameter '{first_param}' doesn't suggest DataFrame input"


class TestColumnCoverage:
    """Test column coverage and graceful handling of missing columns."""
    
    def test_irr_stats_handles_missing_irr(self):
        """Test IRR stats graceful handling of missing IRR column."""
        # Create empty DataFrame
        df_empty = pd.DataFrame()
        
        result = ui_metrics.irr_stats(df_empty)
        
        # Should return dict with NaN values, not crash
        assert isinstance(result, dict)
        assert 'mean' in result
        assert 'prob_ge_15' in result
        # All values should be NaN
        for key, value in result.items():
            assert pd.isna(value), f"Expected NaN for {key}, got {value}"
    
    def test_return_value_metrics_handles_missing_columns(self):
        """Test return value metrics with various missing columns."""
        # DataFrame with only some columns
        df_partial = pd.DataFrame({
            'CoC': [0.15, 0.18, 0.12],
            'NPV': [1000000, 1200000, 800000]
            # Missing: EquityMultiple, PI
        })
        
        result = ui_metrics.return_value_metrics(df_partial)
        
        # Should return dict without crashing
        assert isinstance(result, dict)
        
        # CoC and NPV should have valid values
        assert not pd.isna(result['coc_mean'])
        assert not pd.isna(result['npv_mean'])
        
        # EquityMultiple should be NaN (missing column)
        assert pd.isna(result['equity_multiple_mean'])
    
    def test_pi_fallback_calculation_works(self):
        """Test PI fallback calculation when PI missing but NPV and Equity available."""
        # DataFrame with NPV and Equity but no PI
        df_fallback = pd.DataFrame({
            'NPV': [1000000, 1200000, 800000],
            'Equity': [5000000, 5000000, 5000000],
            'CoC': [0.15, 0.18, 0.12],
            'EquityMultiple': [1.5, 1.6, 1.4]
        })
        
        result = ui_metrics.return_value_metrics(df_fallback)
        
        # PI should be calculated as (NPV + Equity) / Equity
        expected_pi_mean = ((1000000 + 5000000) / 5000000 + 
                           (1200000 + 5000000) / 5000000 + 
                           (800000 + 5000000) / 5000000) / 3
        
        assert not pd.isna(result['pi_mean'])
        assert abs(result['pi_mean'] - expected_pi_mean) < 1e-6
    
    def test_covenant_minima_fallback_logic(self):
        """Test covenant minima fallback column logic."""
        # DataFrame with fallback DSCR column
        df_fallback = pd.DataFrame({
            'DSCR': [1.5, 1.8, 1.2, 1.6],
            'DebtYield_Y1': [0.12, 0.15, 0.10, 0.14]
            # Missing: MinDSCR, MinDebtYield
        })
        
        result = ui_metrics.covenant_minima(df_fallback)
        
        # Should use fallback columns successfully
        assert not pd.isna(result['min_dscr_mean'])
        assert not pd.isna(result['min_dy_mean_pct'])
        
        # Verify fallback calculation
        expected_dscr_mean = (1.5 + 1.8 + 1.2 + 1.6) / 4
        expected_dy_pct = (0.12 + 0.15 + 0.10 + 0.14) / 4 * 100
        
        assert abs(result['min_dscr_mean'] - expected_dscr_mean) < 1e-6
        assert abs(result['min_dy_mean_pct'] - expected_dy_pct) < 1e-6
    
    def test_prepay_defeasance_boolean_handling(self):
        """Test prepay/defeasance boolean column handling."""
        # DataFrame with boolean columns
        df_bool = pd.DataFrame({
            'Defeasance_Used': [True, False, True, False],
            'PrepayAtSale_Toggle': [False, True, True, False],
            'Defeasance_Cost_Refi': [50000, 0, 60000, 0],
            'Prepay_Cost_Sale': [0, 25000, 30000, 0]
        })
        
        result = ui_metrics.prepay_defeasance(df_bool)
        
        # Should calculate percentages correctly
        expected_def_pct = 50.0  # 2 out of 4 are True
        expected_toggle_pct = 50.0  # 2 out of 4 are True
        
        assert abs(result['defeasance_used_pct'] - expected_def_pct) < 1e-6
        assert abs(result['toggle_on_pct'] - expected_toggle_pct) < 1e-6
    
    def test_operational_metrics_missing_columns_handling(self):
        """Test operational metrics with missing columns."""
        # DataFrame with only some operational columns
        df_partial = pd.DataFrame({
            'GOI': [15000000, 16000000, 14000000],
            'OccupancyRate': [0.85, 0.90, 0.80]
            # Missing: RevenueGrowth_YoY, TenantTurnoverRate, etc.
        })
        
        result = ui_metrics.operational_risk_metrics(df_partial)
        
        # Available columns should have valid values
        assert not pd.isna(result['goi_p50'])
        assert not pd.isna(result['occupancy_rate_p50'])
        
        # Missing columns should return NaN
        assert pd.isna(result['revenue_growth_p50'])
        assert pd.isna(result['tenant_turnover_p50'])


class TestEndToEndFunctionality:
    """Test end-to-end functionality without Streamlit context."""
    
    def test_all_functions_run_without_streamlit(self, df_small_base):
        """Test that all metric functions can run without Streamlit context."""
        # This should work even without Streamlit imports
        functions_to_test = [
            ui_metrics.irr_stats,
            ui_metrics.capex_adj_irr_mean,
            ui_metrics.return_value_metrics,
            ui_metrics.risk_ops_metrics,
            ui_metrics.covenant_minima,
            ui_metrics.prepay_defeasance,
            ui_metrics.operational_risk_metrics,
            ui_metrics.advanced_financial_metrics,
            ui_metrics.financial_ratios_metrics,
            ui_metrics.fifty_percent_rule_metrics,
            ui_metrics.reit_investment_metrics,
            ui_metrics.additional_kpis
        ]
        
        for func in functions_to_test:
            try:
                result = func(df_small_base)
                # Should return a result (dict or float/int)
                assert result is not None
                
                if isinstance(result, dict):
                    # Dict should have at least one key
                    assert len(result) > 0
                elif isinstance(result, (int, float)):
                    # Single value is valid (could be NaN)
                    pass
                else:
                    pytest.fail(f"Function {func.__name__} returned unexpected type: {type(result)}")
                    
            except Exception as e:
                pytest.fail(f"Function {func.__name__} failed: {e}")
    
    def test_consistent_return_types(self, df_small_base):
        """Test that functions return consistent types."""
        # Functions that should return dicts
        dict_functions = [
            ui_metrics.irr_stats,
            ui_metrics.return_value_metrics,
            ui_metrics.risk_ops_metrics,
            ui_metrics.covenant_minima,
            ui_metrics.prepay_defeasance,
            ui_metrics.operational_risk_metrics,
            ui_metrics.advanced_financial_metrics,
            ui_metrics.financial_ratios_metrics,
            ui_metrics.fifty_percent_rule_metrics,
            ui_metrics.reit_investment_metrics,
            ui_metrics.additional_kpis
        ]
        
        for func in dict_functions:
            result = func(df_small_base)
            assert isinstance(result, dict), f"Function {func.__name__} should return dict, got {type(result)}"
        
        # Functions that should return single values
        single_value_functions = [
            ui_metrics.capex_adj_irr_mean
        ]
        
        for func in single_value_functions:
            result = func(df_small_base)
            assert isinstance(result, (int, float)), f"Function {func.__name__} should return number, got {type(result)}"
    
    def test_percentile_functions_return_valid_ranges(self, df_small_base):
        """Test that percentile functions return values in valid ranges."""
        # Test functions that return percentiles
        result = ui_metrics.return_value_metrics(df_small_base)
        
        # Test p5 <= p50 <= p95 for CoC (if available)
        if not pd.isna(result['coc_p5']) and not pd.isna(result['coc_p50']) and not pd.isna(result['coc_p95']):
            assert result['coc_p5'] <= result['coc_p50'] <= result['coc_p95'], \
                f"CoC percentiles not in order: P5={result['coc_p5']}, P50={result['coc_p50']}, P95={result['coc_p95']}"
    
    def test_percentage_metrics_in_valid_range(self, df_small_base):
        """Test that percentage metrics return values in reasonable ranges."""
        # Test prepay/defeasance percentages
        result = ui_metrics.prepay_defeasance(df_small_base)
        
        percentage_keys = ['defeasance_used_pct', 'prepay_sale_used_pct', 'toggle_on_pct']
        
        for key in percentage_keys:
            if key in result and not pd.isna(result[key]):
                value = result[key]
                assert 0.0 <= value <= 100.0, f"{key} should be 0-100%, got {value}"


class TestUIIntegrationReadiness:
    """Test readiness for UI integration."""
    
    def test_can_import_in_ui_context(self):
        """Test that ui_metrics can be imported in a UI-like context."""
        try:
            # Simulate UI import
            import ui_metrics as ui_m
            
            # Should be able to access functions
            assert hasattr(ui_m, 'irr_stats')
            assert callable(ui_m.irr_stats)
            
        except ImportError as e:
            pytest.fail(f"Failed to import ui_metrics in UI context: {e}")
    
    def test_functions_handle_empty_dataframes(self):
        """Test that functions handle edge cases like empty DataFrames."""
        df_empty = pd.DataFrame()
        
        # All functions should handle empty DataFrames gracefully
        functions = [
            ui_metrics.irr_stats,
            ui_metrics.capex_adj_irr_mean,
            ui_metrics.return_value_metrics,
            ui_metrics.risk_ops_metrics,
            ui_metrics.covenant_minima,
            ui_metrics.prepay_defeasance
        ]
        
        for func in functions:
            try:
                result = func(df_empty)
                # Should not crash
                assert result is not None
            except Exception as e:
                pytest.fail(f"Function {func.__name__} failed on empty DataFrame: {e}")
    
    def test_functions_handle_nan_data(self):
        """Test that functions handle DataFrames with all NaN data."""
        import numpy as np
        
        # DataFrame with NaN values
        df_nan = pd.DataFrame({
            'IRR': [np.nan, np.nan, np.nan],
            'CoC': [np.nan, np.nan, np.nan],
            'NPV': [np.nan, np.nan, np.nan]
        })
        
        # Should handle gracefully
        irr_result = ui_metrics.irr_stats(df_nan)
        return_result = ui_metrics.return_value_metrics(df_nan)
        
        # Results should be NaN but not crash
        assert all(pd.isna(v) for v in irr_result.values())
        
        # Check nested structure for return_result
        canonical_metrics = ['coc', 'equity_multiple', 'npv', 'profitability_index']
        for metric in canonical_metrics:
            if metric in return_result:
                metric_data = return_result[metric]
                assert all(pd.isna(v) for v in metric_data.values()), f"All {metric} stats should be NaN"


class TestMemoryAndPerformance:
    """Test memory usage and performance characteristics."""
    
    def test_functions_dont_modify_input_dataframe(self, df_small_base):
        """Test that metric functions don't modify the input DataFrame."""
        # Create a copy to compare
        df_original = df_small_base.copy()
        
        # Run a function that processes the DataFrame
        ui_metrics.return_value_metrics(df_small_base)
        
        # DataFrame should be unchanged
        pd.testing.assert_frame_equal(df_small_base, df_original)
    
    def test_functions_are_memory_efficient(self, df_small_base):
        """Test that functions don't create excessive memory usage."""
        import sys
        import gc
        
        # Get initial memory usage
        initial_objects = len(gc.get_objects()) if 'gc' in sys.modules else 0
        
        # Run several functions
        ui_metrics.irr_stats(df_small_base)
        ui_metrics.return_value_metrics(df_small_base)
        ui_metrics.risk_ops_metrics(df_small_base)
        
        # Memory usage shouldn't explode
        # (This is a basic test - in practice you'd use memory profiling tools)
        if 'gc' in sys.modules:
            import gc
            final_objects = len(gc.get_objects())
            # Allow some reasonable growth
            assert final_objects < initial_objects + 1000, "Excessive memory usage detected"
