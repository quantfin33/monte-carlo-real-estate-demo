"""
Seed Registry - Centralized seed management for reproducible testing.

This module provides fixed seeds for different types of tests to ensure
reproducible results across test runs and environments.
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class SeedSet:
    """A set of seeds for different test scenarios."""
    base: int
    property_tests: int
    mutation_tests: int
    invariant_tests: int
    sensitivity_tests: int
    integration_tests: int


# Primary seed set for all testing
TEST_SEEDS = SeedSet(
    base=42,
    property_tests=1337,
    mutation_tests=2023,
    invariant_tests=8888,
    sensitivity_tests=9999,
    integration_tests=5555
)

# Specific seeds for different scenarios
SCENARIO_SEEDS: Dict[str, int] = {
    'high_performance': 12345,
    'stress_test': 67890,
    'edge_cases': 11111,
    'baseline': TEST_SEEDS.base,
    'regression': 98765
}


def get_test_seed(test_type: str = 'base') -> int:
    """
    Get appropriate seed for a test type.
    
    Args:
        test_type: Type of test ('base', 'property', 'mutation', 'invariant', 'sensitivity', 'integration')
        
    Returns:
        Seed value for the test type
    """
    seed_map = {
        'base': TEST_SEEDS.base,
        'property': TEST_SEEDS.property_tests,
        'mutation': TEST_SEEDS.mutation_tests,
        'invariant': TEST_SEEDS.invariant_tests,
        'sensitivity': TEST_SEEDS.sensitivity_tests,
        'integration': TEST_SEEDS.integration_tests
    }
    
    return seed_map.get(test_type, TEST_SEEDS.base)


def get_scenario_seed(scenario: str) -> int:
    """
    Get seed for a specific test scenario.
    
    Args:
        scenario: Scenario name
        
    Returns:
        Seed value for the scenario
    """
    return SCENARIO_SEEDS.get(scenario, TEST_SEEDS.base)


def get_all_seeds() -> Dict[str, Any]:
    """Get all available seeds for debugging/logging purposes."""
    return {
        'test_seeds': TEST_SEEDS,
        'scenario_seeds': SCENARIO_SEEDS
    }
