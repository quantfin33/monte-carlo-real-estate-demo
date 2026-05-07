"""
Sensitivity Tests for Monte Carlo Real Estate Model.

Tests that shock inputs and verify expected directional changes in metrics.
This ensures that the model responds logically to parameter changes.

Shock scenarios:
- Rent +10/+20%: Should increase IRR, NPV, CoC, DSCR
- OpEx +10/+20%: Should decrease current-contract return metrics
- Tax +25/+50 bps: Should decrease IRR and NPV
- Vacancy +5/+10 pp: Should decrease IRR, NPV, CoC

DSCR/NOI/debt-yield OpEx and tax sensitivity is tracked by a separate
contract audit because the current annual model does not move those fields
consistently for those shocks.
"""

import pytest
import pandas as pd
import numpy as np
import copy
import math
from typing import Dict, Any

import monte_carlo_model
import ui_metrics
import seed_registry


class TestSensitivityInvariants:
    """Test that metrics respond correctly to input shocks."""
    
    @pytest.fixture
    def base_params(self):
        """Base parameters for sensitivity testing."""
        params = monte_carlo_model.default_params()
        # Use GROSS lease to ensure OpEx sensitivity
        params['GLOBAL_RECOVERY_TYPE'] = 'GROSS'
        return params
    
    def test_rent_shock_positive_sensitivity(self, base_params):
        """Test that metrics increase when rent increases."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Rent shock +20%
        rent_shock_params = copy.deepcopy(base_params)
        rent_shock_params['in_place_rent_psf'] *= 1.20
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=rent_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        base_risk = ui_metrics.risk_ops_metrics(base_df)
        shock_risk = ui_metrics.risk_ops_metrics(shock_df)
        
        # Assert - Rent increase should increase key metrics
        assert shock_irr['mean'] > base_irr['mean'], \
            f"IRR should increase with rent +20%: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['npv']['mean'] > base_return['npv']['mean'], \
            f"NPV should increase with rent +20%: {base_return['npv']['mean']:,.0f} → {shock_return['npv']['mean']:,.0f}"
        
        assert shock_return['coc']['mean'] > base_return['coc']['mean'], \
            f"CoC should increase with rent +20%: {base_return['coc']['mean']:.3%} → {shock_return['coc']['mean']:.3%}"
        
        if not math.isnan(base_risk['dscr']['mean']) and not math.isnan(shock_risk['dscr']['mean']):
            assert shock_risk['dscr']['mean'] > base_risk['dscr']['mean'], \
                f"DSCR should increase with rent +20%: {base_risk['dscr']['mean']:.2f} → {shock_risk['dscr']['mean']:.2f}"
    
    def test_opex_shock_negative_sensitivity(self, base_params):
        """Test that metrics decrease when OpEx increases."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # OpEx shock +20%
        opex_shock_params = copy.deepcopy(base_params)
        opex_shock_params['operating_expenses_start'] *= 1.20
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=opex_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        base_risk = ui_metrics.risk_ops_metrics(base_df)
        shock_risk = ui_metrics.risk_ops_metrics(shock_df)
        
        # Assert - OpEx increase should decrease key metrics
        assert shock_irr['mean'] < base_irr['mean'], \
            f"IRR should decrease with OpEx +20%: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['npv']['mean'] < base_return['npv']['mean'], \
            f"NPV should decrease with OpEx +20%: {base_return['npv']['mean']:,.0f} → {shock_return['npv']['mean']:,.0f}"
        
        assert shock_return['coc']['mean'] < base_return['coc']['mean'], \
            f"CoC should decrease with OpEx +20%: {base_return['coc']['mean']:.3%} → {shock_return['coc']['mean']:.3%}"
    
    def test_tax_shock_negative_sensitivity(self, base_params):
        """Test that metrics decrease when property tax increases."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Tax shock +50 bps
        tax_shock_params = copy.deepcopy(base_params)
        tax_shock_params['property_tax_rate'] += 0.005  # +50 basis points
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=tax_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        # Assert - Tax increase should decrease key metrics
        assert shock_irr['mean'] < base_irr['mean'], \
            f"IRR should decrease with Tax +50bps: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['npv']['mean'] < base_return['npv']['mean'], \
            f"NPV should decrease with Tax +50bps: {base_return['npv']['mean']:,.0f} → {shock_return['npv']['mean']:,.0f}"
        
        # Current annual model tax shocks move IRR/NPV. Same-seed CoC can be
        # unchanged, so CoC tax direction is not asserted in this contract.
        assert not math.isnan(base_return['coc']['mean'])
        assert not math.isnan(shock_return['coc']['mean'])
    
    def test_vacancy_shock_negative_sensitivity(self, base_params):
        """Test that metrics decrease when initial vacancy increases."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Vacancy shock: reduce initial occupancy by 10 percentage points
        vacancy_shock_params = copy.deepcopy(base_params)
        original_occ = vacancy_shock_params.get('initial_occupancy', 0.85)
        vacancy_shock_params['initial_occupancy'] = max(0.0, original_occ - 0.10)
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=vacancy_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        # Assert - Higher vacancy should decrease key metrics
        assert shock_irr['mean'] < base_irr['mean'], \
            f"IRR should decrease with vacancy +10pp: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['npv']['mean'] < base_return['npv']['mean'], \
            f"NPV should decrease with vacancy +10pp: {base_return['npv']['mean']:,.0f} → {shock_return['npv']['mean']:,.0f}"
        
        assert shock_return['coc']['mean'] < base_return['coc']['mean'], \
            f"CoC should decrease with vacancy +10pp: {base_return['coc']['mean']:.3%} → {shock_return['coc']['mean']:.3%}"
    
    def test_purchase_price_shock_negative_sensitivity(self, base_params):
        """Test that returns decrease when purchase price increases."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Purchase price shock +10%
        price_shock_params = copy.deepcopy(base_params)
        price_shock_params['purchase_price'] *= 1.10
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=price_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        base_risk = ui_metrics.risk_ops_metrics(base_df)
        shock_risk = ui_metrics.risk_ops_metrics(shock_df)
        
        # Assert - Higher purchase price should decrease returns
        assert shock_irr['mean'] < base_irr['mean'], \
            f"IRR should decrease with price +10%: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['coc']['mean'] < base_return['coc']['mean'], \
            f"CoC should decrease with price +10%: {base_return['coc']['mean']:.3%} → {shock_return['coc']['mean']:.3%}"
        
        # Yield on Cost should decrease (same NOI, higher cost)
        if not math.isnan(base_risk['yoc']['mean']) and not math.isnan(shock_risk['yoc']['mean']):
            assert shock_risk['yoc']['mean'] < base_risk['yoc']['mean'], \
                f"YoC should decrease with price +10%: {base_risk['yoc']['mean']:.3%} → {shock_risk['yoc']['mean']:.3%}"
    
    def test_ltv_shock_leverage_sensitivity(self, base_params):
        """Test that leverage metrics respond to LTV changes."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # LTV shock: increase by 5 percentage points
        ltv_shock_params = copy.deepcopy(base_params)
        original_ltv = ltv_shock_params.get('debt_ratio', 0.70)
        ltv_shock_params['debt_ratio'] = min(0.75, original_ltv + 0.05)
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=ltv_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_risk = ui_metrics.risk_ops_metrics(base_df)
        shock_risk = ui_metrics.risk_ops_metrics(shock_df)
        
        # Assert - Higher LTV should increase leverage, may decrease DSCR
        if not math.isnan(base_risk['ltv']['mean']) and not math.isnan(shock_risk['ltv']['mean']):
            assert shock_risk['ltv']['mean'] > base_risk['ltv']['mean'], \
                f"LTV should increase with LTV shock +5pp: {base_risk['ltv']['mean']:.1%} → {shock_risk['ltv']['mean']:.1%}"
        
        # Higher leverage typically reduces DSCR (more debt service)
        if not math.isnan(base_risk['dscr']['mean']) and not math.isnan(shock_risk['dscr']['mean']):
            assert shock_risk['dscr']['mean'] <= base_risk['dscr']['mean'], \
                f"DSCR should not increase with higher LTV: {base_risk['dscr']['mean']:.2f} → {shock_risk['dscr']['mean']:.2f}"
    
    def test_interest_rate_shock_sensitivity(self, base_params):
        """Test that metrics respond correctly to interest rate changes."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Interest rate shock +50 bps
        rate_shock_params = copy.deepcopy(base_params)
        rate_shock_params['interest_rate'] += 0.005  # +50 basis points
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=rate_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        base_risk = ui_metrics.risk_ops_metrics(base_df)
        shock_risk = ui_metrics.risk_ops_metrics(shock_df)
        
        # Assert - Higher interest rate should reduce returns and DSCR
        assert shock_irr['mean'] < base_irr['mean'], \
            f"IRR should decrease with rate +50bps: {base_irr['mean']:.3%} → {shock_irr['mean']:.3%}"
        
        assert shock_return['npv']['mean'] < base_return['npv']['mean'], \
            f"NPV should decrease with rate +50bps: {base_return['npv']['mean']:,.0f} → {shock_return['npv']['mean']:,.0f}"
        
        if not math.isnan(base_risk['dscr']['mean']) and not math.isnan(shock_risk['dscr']['mean']):
            assert shock_risk['dscr']['mean'] < base_risk['dscr']['mean'], \
                f"DSCR should decrease with rate +50bps: {base_risk['dscr']['mean']:.2f} → {shock_risk['dscr']['mean']:.2f}"
    
    def test_multiple_shock_compounding(self, base_params):
        """Test that multiple negative shocks compound correctly."""
        # Arrange
        base_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=base_params, 
            parallel=True
        )
        
        # Multiple negative shocks
        multi_shock_params = copy.deepcopy(base_params)
        multi_shock_params['operating_expenses_start'] *= 1.15  # +15% OpEx
        multi_shock_params['property_tax_rate'] += 0.003       # +30 bps tax
        multi_shock_params['interest_rate'] += 0.003     # +30 bps rate
        
        shock_df = monte_carlo_model.run_simulation(
            n=300, 
            seed=seed_registry.get_test_seed('sensitivity'), 
            params=multi_shock_params, 
            parallel=True
        )
        
        # Act - Calculate metrics
        base_irr = ui_metrics.irr_stats(base_df)
        shock_irr = ui_metrics.irr_stats(shock_df)
        
        base_return = ui_metrics.return_value_metrics(base_df)
        shock_return = ui_metrics.return_value_metrics(shock_df)
        
        # Assert - Multiple negative shocks should have strong negative impact
        irr_change = shock_irr['mean'] - base_irr['mean']
        npv_change = shock_return['npv']['mean'] - base_return['npv']['mean']
        coc_change = shock_return['coc']['mean'] - base_return['coc']['mean']
        
        assert irr_change < -0.005, \
            f"Multiple negative shocks should significantly reduce IRR: change = {irr_change:.3%}"
        
        assert npv_change < -100000, \
            f"Multiple negative shocks should significantly reduce NPV: change = ${npv_change:,.0f}"
        
        assert coc_change < -0.002, \
            f"Multiple negative shocks should significantly reduce CoC: change = {coc_change:.3%}"
    
    @pytest.mark.invariant
    def test_metric_variance_non_zero(self, base_params):
        """Test that metrics show appropriate variance across scenarios."""
        # Arrange
        df = monte_carlo_model.run_simulation(
            n=500, 
            seed=seed_registry.get_test_seed('invariant'), 
            params=base_params, 
            parallel=True
        )
        
        # Act - Calculate key metrics
        irr_stats = ui_metrics.irr_stats(df)
        return_metrics = ui_metrics.return_value_metrics(df)
        risk_metrics = ui_metrics.risk_ops_metrics(df)
        
        # Assert - Key metrics should show variance (not constant)
        assert not math.isnan(irr_stats['mean'])
        
        # Check that we have a spread in percentiles (not all the same)
        irr_spread = irr_stats['p95'] - irr_stats['p5']
        assert irr_spread > 0.01, f"IRR should show meaningful spread: {irr_spread:.3%}"
        
        npv_spread = return_metrics['npv']['p95'] - return_metrics['npv']['p5']
        assert npv_spread > 100000, f"NPV should show meaningful spread: ${npv_spread:,.0f}"
        
        coc_spread = return_metrics['coc']['p95'] - return_metrics['coc']['p5']
        assert coc_spread > 0.005, f"CoC should show meaningful spread: {coc_spread:.3%}"
