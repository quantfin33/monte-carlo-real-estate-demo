"""
Pytest configuration and shared fixtures for Monte Carlo Model testing
"""

import pytest
import copy
import numpy as np
import pandas as pd
import tempfile
import os
from pathlib import Path

# Add the project directory to Python path
import sys
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

try:
    import rmc_model as m
except ImportError:
    pytest.skip("rmc_model not available", allow_module_level=True)

@pytest.fixture(scope="session")
def base_params():
    """Base parameters for all tests"""
    return copy.deepcopy(m.default_params())

@pytest.fixture(scope="function")
def test_params(base_params):
    """Fresh copy of base parameters for each test"""
    params = copy.deepcopy(base_params)
    params['_seed'] = 42  # Fixed seed for reproducible tests
    params['refi_year'] = 0  # No refi to isolate other effects
    return params

@pytest.fixture(scope="function")
def small_simulation_params(test_params):
    """Parameters optimized for fast testing"""
    params = copy.deepcopy(test_params)
    params['_seed'] = 123
    return params

@pytest.fixture(scope="session")
def temp_dir():
    """Temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir

@pytest.fixture(scope="function")
def mock_ui_session_state():
    """Mock UI session state for testing"""
    return {
        'sims': 1000,
        'seed': 42,
        'in_place_rent_psf': 23.64,
        'total_rsf': 630594,
        'initial_occupancy': 0.826,
        'market_rent_psf': 27.0,
        'purchase_price': 108000000,
        'operating_expenses_start': 2500000,
        'opex_growth_rate': 0.03,
        'property_tax_rate': 0.015,
        'tax_mode': 'independent',
        'tax_growth_rate': 0.025,
        'debt_ratio': 0.45,
        'interest_rate': 0.0675,
        'refi_year': 5,
        'refi_cost_rate': 0.025,
        'interest_only_years': 2,
        'amort_years': 25,
        'recovery_type': 'NNN',
        'reserve_per_rsf': 0.25,
        'reserve_start_year': 1,
        'reserve_escalation': 0.03,
        'reserve_policy': 'offset_building',
        'prepay': {
            'model': 'defeasance',
            'lockout_years': 0,
            'stepdown': {1: 0.05, 2: 0.04, 3: 0.03, 4: 0.02, 5: 0.01},
            'ym_spread': 0.02,
            'defeasance_open_year': None,
            'df_method': 'flat',
            'rf_flat_rate': 0.045,
            'rf_curve': {1: 0.043, 2: 0.044, 3: 0.05},
            'fees_bps': 30
        },
        'prepay_at_sale': True,
        'debug_return_schedule': False
    }

@pytest.fixture(scope="function")
def expected_irr_range():
    """Expected IRR range for validation tests"""
    return (0.15, 0.25)  # 15% to 25% IRR

@pytest.fixture(scope="function")
def expected_npv_range():
    """Expected NPV range for validation tests"""
    return (20000000, 80000000)  # $20M to $80M NPV

@pytest.fixture(scope="function")
def tolerance():
    """Tolerance for floating point comparisons"""
    return 1e-6

@pytest.fixture(scope="function")
def timeout_seconds():
    """Timeout for long-running tests"""
    return 30

# Test markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "ui: marks tests as UI tests"
    )
    config.addinivalue_line(
        "markers", "model: marks tests as model tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )

# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names"""
    for item in items:
        if "test_ui" in item.name:
            item.add_marker(pytest.mark.ui)
        elif "test_model" in item.name:
            item.add_marker(pytest.mark.model)
        elif "test_performance" in item.name:
            item.add_marker(pytest.mark.performance)
        elif "test_integration" in item.name:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
