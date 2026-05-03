"""
Pytest configuration and fixtures for Monte Carlo real estate model testing.

Provides fixtures for:
- engine_defaults() → deep copy of rmc_model.default_params()
- df_base() → baseline simulation results DataFrame
- df_shock_rent_up() → rent increased by +20% scenario
- df_shock_opex_up() → operating expenses increased by +20% scenario

All fixtures use deterministic seeds and parallel=True to match UI behavior.
"""

import pytest
import copy
import pandas as pd
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import rmc_model
import seed_registry


@pytest.fixture(scope="session")
def engine_defaults():
    """
    Get a deep copy of default engine parameters.
    
    Returns:
        dict: Deep copy of rmc_model.default_params()
    """
    return copy.deepcopy(rmc_model.default_params())


@pytest.fixture(scope="session")
def df_base(engine_defaults):
    """
    Generate baseline simulation results.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: Baseline simulation results (n=2000, seed=123)
    """
    return rmc_model.run_simulation(
        n=2000, 
        seed=123, 
        params=engine_defaults, 
        parallel=True
    )


@pytest.fixture(scope="session")
def df_shock_rent_up(engine_defaults):
    """
    Generate simulation results with rent shocked up by +20%.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: Rent shock simulation results (n=2000, seed=123)
    """
    params = copy.deepcopy(engine_defaults)
    
    # Increase in-place rent by 20%
    original_rent = params.get('in_place_rent_psf', 30.0)
    params['in_place_rent_psf'] = original_rent * 1.2
    
    return rmc_model.run_simulation(
        n=2000, 
        seed=123, 
        params=params, 
        parallel=True
    )


@pytest.fixture(scope="session")
def df_shock_opex_up(engine_defaults):
    """
    Generate simulation results with operating expenses shocked up by +20%.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: OpEx shock simulation results (n=2000, seed=123)
    """
    params = copy.deepcopy(engine_defaults)
    
    # Increase operating expenses by 20%
    original_opex = params.get('operating_expenses_start', 2500000.0)
    params['operating_expenses_start'] = original_opex * 1.2
    
    return rmc_model.run_simulation(
        n=2000, 
        seed=123, 
        params=params, 
        parallel=True
    )


@pytest.fixture(scope="session")
def df_small_base(engine_defaults):
    """
    Generate small baseline simulation for quick tests.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: Small baseline simulation results (n=100, seed=42)
    """
    return rmc_model.run_simulation(
        n=100, 
        seed=42, 
        params=engine_defaults, 
        parallel=True
    )


@pytest.fixture(scope="session")
def df_small_rent_shock(engine_defaults):
    """
    Generate small simulation with rent shock for quick tests.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: Small rent shock simulation results (n=100, seed=42)
    """
    params = copy.deepcopy(engine_defaults)
    
    # Increase in-place rent by 20%
    original_rent = params.get('in_place_rent_psf', 30.0)
    params['in_place_rent_psf'] = original_rent * 1.2
    
    return rmc_model.run_simulation(
        n=100, 
        seed=42, 
        params=params, 
        parallel=True
    )


@pytest.fixture
def sample_metrics_data():
    """Sample DataFrame for testing metrics functions directly."""
    np.random.seed(seed_registry.get_test_seed('base'))
    
    # Create realistic sample data for testing ui_metrics functions
    data = {
        'IRR': np.random.normal(0.12, 0.03, 100),
        'CoC': np.random.normal(0.08, 0.02, 100),
        'NPV': np.random.normal(5000000, 2000000, 100),
        'EquityMultiple': np.random.normal(1.8, 0.3, 100),
        'DSCR': np.random.normal(1.4, 0.2, 100),
        'LTV': np.random.normal(0.65, 0.05, 100),
        'YieldOnCost': np.random.normal(0.06, 0.01, 100),
        'DebtYield_Y1': np.random.normal(0.09, 0.015, 100),
        'MinDebtYield': np.random.normal(0.08, 0.02, 100),
        'CapRate': np.random.normal(0.055, 0.01, 100),
        'FFO': np.random.normal(8000000, 1500000, 100),
        'AFFO': np.random.normal(7000000, 1400000, 100),
        'NAV': np.random.normal(120000000, 20000000, 100),
    }
    
    return pd.DataFrame(data)


@pytest.fixture(scope="session")
def df_small_opex_shock(engine_defaults):
    """
    Generate small simulation with OpEx shock for quick tests.
    
    Args:
        engine_defaults: Default parameters from engine_defaults fixture
        
    Returns:
        pd.DataFrame: Small OpEx shock simulation results (n=100, seed=42)
    """
    params = copy.deepcopy(engine_defaults)
    
    # Increase operating expenses by 20%
    original_opex = params.get('operating_expenses_start', 2500000.0)
    params['operating_expenses_start'] = original_opex * 1.2
    
    return rmc_model.run_simulation(
        n=100, 
        seed=42, 
        params=params, 
        parallel=True
    )


@pytest.fixture
def sample_metrics_data():
    """Sample DataFrame for testing metrics functions directly."""
    np.random.seed(seed_registry.get_test_seed('base'))
    
    # Create realistic sample data for testing ui_metrics functions
    data = {
        'IRR': np.random.normal(0.12, 0.03, 100),
        'CoC': np.random.normal(0.08, 0.02, 100),
        'NPV': np.random.normal(5000000, 2000000, 100),
        'EquityMultiple': np.random.normal(1.8, 0.3, 100),
        'DSCR': np.random.normal(1.4, 0.2, 100),
        'LTV': np.random.normal(0.65, 0.05, 100),
        'YieldOnCost': np.random.normal(0.06, 0.01, 100),
        'DebtYield_Y1': np.random.normal(0.09, 0.015, 100),
        'MinDebtYield': np.random.normal(0.08, 0.02, 100),
        'CapRate': np.random.normal(0.055, 0.01, 100),
        'FFO': np.random.normal(8000000, 1500000, 100),
        'AFFO': np.random.normal(7000000, 1400000, 100),
        'NAV': np.random.normal(120000000, 20000000, 100),
    }
    
    return pd.DataFrame(data)
