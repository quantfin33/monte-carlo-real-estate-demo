"""
DSCR Wiring Tests - Financial Metric Sensitivity Contract v1.

These tests keep DSCR output and variance coverage in the broad suite. GROSS
recovery mode means expenses are not recovered from tenants, so OpEx/tax shocks
must flow through Year 1 NOI and DSCR.
"""

import pytest
import sys
import copy
import math
from pathlib import Path
import pandas as pd
import numpy as np

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import monte_carlo_model


class TestDSCRWiring:
    """Test DSCR sensitivity to input changes."""
    
    @pytest.fixture
    def base_params(self):
        """Base parameters for DSCR testing."""
        params = monte_carlo_model.default_params()
        # PRIORITY-1 FIX: Use GROSS lease to test OpEx sensitivity 
        params['GLOBAL_RECOVERY_TYPE'] = 'GROSS'
        return params
    
    def test_dscr_moves_with_opex(self, base_params):
        """Verify DSCR decreases when unrecovered OpEx increases by 20%."""
        print("\n🧪 TESTING: DSCR vs OpEx +20%")
        
        # Base case
        base_df = monte_carlo_model.run_simulation(n=100, seed=42, params=base_params, parallel=True)
        base_dscr = pd.to_numeric(base_df['DSCR'], errors='coerce').dropna()
        base_dscr_mean = float(base_dscr.mean())
        base_dscr_p50 = float(base_dscr.median())
        base_noi = pd.to_numeric(base_df['NOI_Y1'], errors='coerce').dropna().mean()
        base_irr = pd.to_numeric(base_df['IRR'], errors='coerce').dropna().mean()
        
        print(f"📊 BASE CASE:")
        print(f"   DSCR Mean: {base_dscr_mean:.3f}")
        print(f"   DSCR P50:  {base_dscr_p50:.3f}")
        print(f"   NOI Y1:    ${base_noi:,.0f}")
        print(f"   OpEx:      ${base_params['operating_expenses_start']:,.0f}")
        
        # OpEx shock: +20%
        shocked_params = copy.deepcopy(base_params)
        shocked_params['operating_expenses_start'] = base_params['operating_expenses_start'] * 1.20
        
        shocked_df = monte_carlo_model.run_simulation(n=100, seed=42, params=shocked_params, parallel=True)
        shocked_dscr = pd.to_numeric(shocked_df['DSCR'], errors='coerce').dropna()
        shocked_dscr_mean = float(shocked_dscr.mean())
        shocked_dscr_p50 = float(shocked_dscr.median())
        shocked_noi = pd.to_numeric(shocked_df['NOI_Y1'], errors='coerce').dropna().mean()
        shocked_irr = pd.to_numeric(shocked_df['IRR'], errors='coerce').dropna().mean()
        
        print(f"📊 OPEX +20% CASE:")
        print(f"   DSCR Mean: {shocked_dscr_mean:.3f}")
        print(f"   DSCR P50:  {shocked_dscr_p50:.3f}") 
        print(f"   NOI Y1:    ${shocked_noi:,.0f}")
        print(f"   OpEx:      ${shocked_params['operating_expenses_start']:,.0f}")
        
        # Calculate changes
        dscr_change = shocked_dscr_mean - base_dscr_mean
        noi_change = shocked_noi - base_noi
        
        print(f"📈 CHANGES:")
        print(f"   DSCR Change: {dscr_change:+.3f}")
        print(f"   NOI Change:  ${noi_change:+,.0f}")
        
        # Variance check - DSCR should vary across scenarios
        dscr_variance = base_dscr.var()
        print(f"📊 VARIANCE CHECK:")
        print(f"   DSCR Variance: {dscr_variance:.6f}")
        assert dscr_variance > 1e-6, f"DSCR appears constant (variance={dscr_variance:.6f})"
        
        assert shocked_irr < base_irr, "OpEx shock should still reduce current-contract return metrics"
        assert shocked_noi < base_noi, "GROSS OpEx shock should reduce NOI_Y1"
        assert shocked_dscr_mean < base_dscr_mean, "GROSS OpEx shock should reduce DSCR"
        
        print("✅ DSCR decreases under unrecovered OpEx increase")
    
    def test_dscr_moves_with_tax(self, base_params):
        """Verify DSCR decreases when unrecovered property tax increases by 50bps."""
        print("\n🧪 TESTING: DSCR vs Tax Rate +50bps")
        
        # Base case
        base_df = monte_carlo_model.run_simulation(n=100, seed=42, params=base_params, parallel=True)
        base_dscr = pd.to_numeric(base_df['DSCR'], errors='coerce').dropna()
        base_dscr_mean = float(base_dscr.mean())
        base_npv = pd.to_numeric(base_df['NPV'], errors='coerce').dropna().mean()
        
        print(f"📊 BASE CASE:")
        print(f"   DSCR Mean: {base_dscr_mean:.3f}")
        print(f"   Tax Rate:  {base_params['property_tax_rate']:.1%}")
        
        # Tax shock: +50bps (0.5%)
        shocked_params = copy.deepcopy(base_params)
        shocked_params['property_tax_rate'] = base_params['property_tax_rate'] + 0.005
        
        shocked_df = monte_carlo_model.run_simulation(n=100, seed=42, params=shocked_params, parallel=True)
        shocked_dscr = pd.to_numeric(shocked_df['DSCR'], errors='coerce').dropna()
        shocked_dscr_mean = float(shocked_dscr.mean())
        shocked_npv = pd.to_numeric(shocked_df['NPV'], errors='coerce').dropna().mean()
        
        print(f"📊 TAX +50BPS CASE:")
        print(f"   DSCR Mean: {shocked_dscr_mean:.3f}")
        print(f"   Tax Rate:  {shocked_params['property_tax_rate']:.1%}")
        
        # Calculate change
        dscr_change = shocked_dscr_mean - base_dscr_mean
        print(f"📈 CHANGE:")
        print(f"   DSCR Change: {dscr_change:+.3f}")
        
        assert shocked_npv < base_npv, "Tax shock should still reduce current-contract value metrics"
        assert shocked_dscr_mean < base_dscr_mean, "GROSS tax shock should reduce DSCR"
        
        print("✅ DSCR decreases under unrecovered tax increase")
    
    def test_dscr_variance_exists(self, base_params):
        """Test that DSCR shows variance across Monte Carlo scenarios."""
        print("\n🧪 TESTING: DSCR Variance Across Scenarios")
        
        df = monte_carlo_model.run_simulation(n=200, seed=42, params=base_params, parallel=True)
        dscr_series = pd.to_numeric(df['DSCR'], errors='coerce').dropna()
        
        dscr_mean = dscr_series.mean()
        dscr_std = dscr_series.std()
        dscr_min = dscr_series.min()
        dscr_max = dscr_series.max()
        dscr_range = dscr_max - dscr_min
        
        print(f"📊 DSCR STATISTICS:")
        print(f"   Mean:  {dscr_mean:.3f}")
        print(f"   Std:   {dscr_std:.3f}")
        print(f"   Min:   {dscr_min:.3f}")
        print(f"   Max:   {dscr_max:.3f}")
        print(f"   Range: {dscr_range:.3f}")
        
        # DSCR should not be constant across scenarios
        assert dscr_std > 0.01, f"DSCR shows minimal variance (std={dscr_std:.4f})"
        assert dscr_range > 0.05, f"DSCR range too small (range={dscr_range:.4f})"
        
        print("✅ DSCR shows appropriate variance across scenarios")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
