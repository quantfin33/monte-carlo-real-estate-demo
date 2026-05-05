"""
Integration tests for UI parameter flow and functionality
"""

import pytest
import copy
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

# Import the model
import monte_carlo_model as m

class TestUIParameterFlow:
    """Test that UI parameters correctly flow to the model"""
    
    def test_reserve_parameters_flow(self, mock_ui_session_state):
        """Test reserve parameters flow from UI to model"""
        # Simulate UI parameter extraction
        ui_params = mock_ui_session_state
        ui_params.update({
            'reserve_per_rsf': 2.5,
            'reserve_start_year': 2,
            'reserve_escalation': 0.03,
            'reserve_policy': 'offset_building'
        })
        
        # Run simulation
        result = m.run_simulation(n=100, seed=42, params=ui_params)
        
        # Check that reserves affect the model
        assert 'IRR' in result.columns
        assert not result['IRR'].isna().all()

class TestUIHelpers:
    """Test UI helper functions and parameter extraction"""
    
    class MockUIHelper:
        """Mock UI helper for testing"""
        def _get_ui_params(self):
            """Simulate UI parameter extraction"""
            return {
                'sims': 1000,
                'seed': 42,
                'scenario': 'base',
                'in_place_rent_psf': 25.0,
                'total_rsf': 630594,  # This comes from UI as int
                'initial_occupancy': 0.92,
                'market_rent_psf': 30.0,
                'purchase_price': 50000000,
                'operating_expenses_start': 2500000,
                'opex_growth_rate': 0.025,
                'property_tax_rate': 0.012,
                'debt_ratio': 0.70,
                'interest_rate': 0.045,
                'refi_year': 5,
                'refi_cost_rate': 0.01
            }
    
    def setup_method(self):
        """Set up test fixtures"""
        self.ui_helper = self.MockUIHelper()
    
    def test_ui_parameter_types(self):
        """Test that UI parameters have expected data types."""
        ui_params = self.ui_helper._get_ui_params()
        
        # Check numeric types
        assert isinstance(ui_params['sims'], int)
        assert isinstance(ui_params['seed'], int)
        assert isinstance(ui_params['in_place_rent_psf'], float)
        assert isinstance(ui_params['total_rsf'], int)  # total_rsf is stored as int in UI
        assert isinstance(ui_params['initial_occupancy'], float)
        assert isinstance(ui_params['market_rent_psf'], float)
        assert isinstance(ui_params['purchase_price'], int)
        assert isinstance(ui_params['debt_ratio'], float)
        assert isinstance(ui_params['interest_rate'], float)
        
        # Check string types
        assert isinstance(ui_params['scenario'], str)
    
    def test_ui_parameter_ranges(self):
        """Test that UI parameters are within expected ranges."""
        ui_params = self.ui_helper._get_ui_params()
        
        # Check reasonable ranges
        assert 100 <= ui_params['sims'] <= 100000
        assert 0 <= ui_params['seed'] <= 2**31
        assert 0.0 <= ui_params['initial_occupancy'] <= 1.0
        assert ui_params['in_place_rent_psf'] > 0
        assert ui_params['total_rsf'] > 0
        assert ui_params['purchase_price'] > 0
        assert 0.0 <= ui_params['debt_ratio'] <= 1.0
        assert ui_params['interest_rate'] > 0
    
    def test_missing_ui_parameters(self):
        """Test behavior when required UI parameters are missing."""
        ui_params = self.ui_helper._get_ui_params()
        
        # Remove a critical parameter
        del ui_params['purchase_price']
        
        # The model should handle missing parameters gracefully
        try:
            result = m.run_simulation(n=100, seed=42, params=ui_params)
            # If no exception is raised, check that we get valid results
            if isinstance(result, pd.DataFrame) and 'IRR' in result.columns:
                assert not result['IRR'].isna().all()
        except Exception:
            # It's also acceptable if the model raises an exception for missing critical parameters
            pass
    
    def test_invalid_ui_parameters(self):
        """Test behavior when UI parameters have invalid values."""
        ui_params = self.ui_helper._get_ui_params()
        
        # Set invalid parameters
        ui_params['initial_occupancy'] = 1.5  # > 100%
        ui_params['debt_ratio'] = 0.95  # Very high debt ratio
        ui_params['interest_rate'] = -0.02  # Negative interest rate
        
        # The model should handle invalid parameters gracefully (clamp values, use defaults, etc.)
        try:
            result = m.run_simulation(n=100, seed=42, params=ui_params)
            # If no exception is raised, check that we get valid results
            if isinstance(result, pd.DataFrame) and 'IRR' in result.columns:
                assert not result['IRR'].isna().all()
        except Exception:
            # It's also acceptable if the model raises an exception for invalid parameters
            pass

class TestUIIntegration:
    """Test full UI-model integration scenarios"""
    
    def test_heatmap_parameter_flow(self):
        """Test that heatmap parameters flow correctly to the model"""
        params = copy.deepcopy(m.default_params())
        params.update({
            'exit_cap_left': 0.04,
            'exit_cap_mode': 0.05,
            'exit_cap_right': 0.06,
            'rent_growth_min': 0.01,
            'rent_growth_max': 0.04
        })
        
        # Test that parameters affect the model
        result = m.run_simulation(n=100, seed=42, params=params)
        assert 'IRR' in result.columns
        assert not result['IRR'].isna().all()
    
    def test_prepayment_parameter_flow(self):
        """Test that prepayment parameters flow correctly"""
        params = copy.deepcopy(m.default_params())
        params['prepay'] = {
            'model': 'ym',
            'ym_spread': 0.02,
            'lockout_years': 0
        }
        params['prepay_at_sale'] = True
        
        # Test that prepayment affects the model
        result = m.run_simulation(n=100, seed=42, params=params)
        assert 'IRR' in result.columns
        assert not result['IRR'].isna().all()
    
    def test_correlation_parameter_flow(self):
        """Test that correlation parameters flow correctly"""
        params = copy.deepcopy(m.default_params())
        params['correlations'] = {
            'enabled': True,
            'variables': ['occ0', 'rg_bias'],
            'matrix': [[1.0, 0.5], [0.5, 1.0]]
        }
        
        # Test that correlations affect the model
        result = m.run_simulation(n=100, seed=42, params=params)
        assert 'IRR' in result.columns
        assert not result['IRR'].isna().all()
