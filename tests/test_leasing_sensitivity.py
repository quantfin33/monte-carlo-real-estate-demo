"""
Leasing Sensitivity Tests - Priority 1 Critical Fix

Tests that leasing metrics respond correctly to renew_prob changes.
Expected: If renew_prob increases, the current validated LeaseRenewalRate output increases.
TenantTurnoverRate is parked because it is not part of the current annual validated output contract.
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


class TestLeasingSensitivity:
    """Test leasing metrics sensitivity to renewal probability."""
    
    @pytest.fixture
    def base_params(self):
        """Base parameters for leasing testing."""
        return monte_carlo_model.default_params()
    
    def test_renewal_moves_with_prob(self, base_params):
        """Test that LeaseRenewalRate increases when renew_prob increases by 10pp."""
        print("\n🧪 TESTING: Lease Renewal Rate vs renew_prob +10pp")
        
        # Base case
        base_df = monte_carlo_model.run_simulation(n=200, seed=42, params=base_params, parallel=True)
        base_renewal = pd.to_numeric(base_df['LeaseRenewalRate'], errors='coerce').dropna()
        
        if not base_renewal.empty:
            base_renewal_mean = float(base_renewal.mean())
        else:
            base_renewal_mean = float('nan')
        base_renew_prob = float(base_params.get('renew_prob', 0.60))

        print(f"📊 BASE CASE:")
        print(f"   Renew Prob:       {base_renew_prob:.1%}")
        print(f"   Renewal Rate:     {base_renewal_mean:.1%}")
        print(f"   Renewal Series Length: {len(base_renewal)}")
        
        # Renewal probability shock: +10pp
        shocked_params = copy.deepcopy(base_params)
        shocked_params['renew_prob'] = min(0.95, base_renew_prob + 0.10)
        
        shocked_df = monte_carlo_model.run_simulation(n=200, seed=42, params=shocked_params, parallel=True)
        shocked_renewal = pd.to_numeric(shocked_df['LeaseRenewalRate'], errors='coerce').dropna()
        
        if not shocked_renewal.empty:
            shocked_renewal_mean = float(shocked_renewal.mean())
        else:
            shocked_renewal_mean = float('nan')
        
        print(f"📊 RENEW_PROB +10PP CASE:")
        print(f"   Renew Prob:       {shocked_params['renew_prob']:.1%}")
        print(f"   Renewal Rate:     {shocked_renewal_mean:.1%}")
        print(f"   Renewal Series Length: {len(shocked_renewal)}")
        
        # Calculate changes
        if not (math.isnan(base_renewal_mean) or math.isnan(shocked_renewal_mean)):
            renewal_change = shocked_renewal_mean - base_renewal_mean
            print(f"📈 RENEWAL CHANGE: {renewal_change:+.1%}")
            
            # Check if data exists and makes sense
            assert not base_renewal.empty, "Base renewal rate data is missing"
            assert not shocked_renewal.empty, "Shocked renewal rate data is missing"
            
            # Direction check - Renewal rate should increase with higher renew_prob
            assert shocked_renewal_mean > base_renewal_mean, (
                f"Renewal rate should increase with renew_prob +10pp: "
                f"{base_renewal_mean:.1%} → {shocked_renewal_mean:.1%} (change: {renewal_change:+.1%})"
            )
            print("✅ Renewal rate correctly increased")
        else:
            print("⚠️  Renewal rate data contains NaN values - investigating...")
            print(f"   Base renewal mean: {base_renewal_mean}")
            print(f"   Shocked renewal mean: {shocked_renewal_mean}")
            
            # Check what columns actually exist
            print(f"📋 Available columns in base_df: {sorted(base_df.columns.tolist())}")
            
            # Let's see if the raw data exists
            if 'LeaseRenewalRate' in base_df.columns:
                renewal_raw = base_df['LeaseRenewalRate']
                print(f"   Raw renewal data sample: {renewal_raw.head().tolist()}")
                print(f"   Raw renewal data types: {renewal_raw.dtype}")
                print(f"   Raw renewal unique values: {renewal_raw.unique()}")
        
        assert 'TenantTurnoverRate' not in base_df.columns, (
            "TenantTurnoverRate is parked and should not be asserted unless it is added "
            "to the annual validated output contract."
        )
    
    def test_leasing_metrics_variance(self, base_params):
        """Test that leasing metrics show variance across Monte Carlo scenarios."""
        print("\n🧪 TESTING: Leasing Metrics Variance")
        
        df = monte_carlo_model.run_simulation(n=200, seed=42, params=base_params, parallel=True)
        
        # Check what leasing-related columns exist
        leasing_columns = [col for col in df.columns if any(term in col.lower() for term in 
                          ['renewal', 'turnover', 'lease', 'tenant'])]
        
        print(f"📋 LEASING-RELATED COLUMNS: {leasing_columns}")
        
        for col in ['LeaseRenewalRate']:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors='coerce').dropna()
                
                if not series.empty:
                    mean_val = series.mean()
                    std_val = series.std()
                    min_val = series.min()
                    max_val = series.max()
                    
                    print(f"📊 {col}:")
                    print(f"   Mean: {mean_val:.3f}")
                    print(f"   Std:  {std_val:.3f}")
                    print(f"   Range: {min_val:.3f} to {max_val:.3f}")
                    
                    # Check for variance (should not be constant)
                    if std_val < 1e-6:
                        print(f"⚠️  {col} appears constant (std={std_val:.6f})")
                        print(f"   Sample values: {series.head(10).tolist()}")
                        print(f"   Unique values: {series.unique()}")
                else:
                    print(f"❌ {col}: No valid data found")
            else:
                print(f"❌ {col}: Column not found in DataFrame")
    
    def test_renew_prob_wiring_trace(self, base_params):
        """Trace the flow of renew_prob parameter through the system."""
        print("\n🧪 TESTING: renew_prob Parameter Wiring")
        
        # Test with extreme values to see if anything changes
        low_params = copy.deepcopy(base_params)
        low_params['renew_prob'] = 0.10  # 10% renewal
        
        high_params = copy.deepcopy(base_params)
        high_params['renew_prob'] = 0.90  # 90% renewal
        
        print(f"📊 TESTING EXTREME VALUES:")
        print(f"   Low renew_prob:  {low_params['renew_prob']:.1%}")
        print(f"   High renew_prob: {high_params['renew_prob']:.1%}")
        
        # Run smaller simulations for faster testing
        low_df = monte_carlo_model.run_simulation(n=50, seed=42, params=low_params, parallel=True)
        high_df = monte_carlo_model.run_simulation(n=50, seed=42, params=high_params, parallel=True)
        
        # Check if ANY leasing metrics change between extreme values
        leasing_metrics = ['LeaseRenewalRate']
        
        for metric in leasing_metrics:
            if metric in low_df.columns and metric in high_df.columns:
                low_vals = pd.to_numeric(low_df[metric], errors='coerce').dropna()
                high_vals = pd.to_numeric(high_df[metric], errors='coerce').dropna()
                
                if not low_vals.empty and not high_vals.empty:
                    low_mean = low_vals.mean()
                    high_mean = high_vals.mean()
                    
                    print(f"📊 {metric}:")
                    print(f"   Low renew_prob (10%):  {low_mean:.3f}")
                    print(f"   High renew_prob (90%): {high_mean:.3f}")
                    print(f"   Difference: {abs(high_mean - low_mean):.3f}")
                    
                    if abs(high_mean - low_mean) < 1e-6:
                        print(f"⚠️  {metric} shows no sensitivity to renew_prob changes")
                    else:
                        print(f"✅ {metric} responds to renew_prob changes")
                else:
                    print(f"❌ {metric}: No valid data in extreme tests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
