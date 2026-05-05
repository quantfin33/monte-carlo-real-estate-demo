from __future__ import annotations

import math

import pytest

import scenario_randomizer as sr


def _base() -> dict:
    return sr.base_reset_inputs()


def test_same_profile_and_seed_are_deterministic():
    first = sr.generate_scenario("Downside", 1234, _base())
    second = sr.generate_scenario("Downside", 1234, _base())

    assert first == second


def test_different_seed_changes_generated_values():
    first = sr.generate_scenario("Base Variation", 1, _base())
    second = sr.generate_scenario("Base Variation", 2, _base())

    assert first["values"] != second["values"]


def test_all_profiles_stay_within_bounds_and_validate():
    for profile in sr.SCENARIO_PROFILES:
        scenario = sr.generate_scenario(profile, 2026, _base())
        values = scenario["values"]

        assert sr.validate_generated_scenario(values) == []
        for key, value in values.items():
            if value is None:
                assert key == "exit_cap_override"
                continue
            assert isinstance(value, (int, float))
            assert math.isfinite(float(value))
            spec = sr.FIELD_SPECS[key]
            assert float(spec["min"]) <= float(value) <= float(spec["max"])


def test_growth_and_exit_cap_ordering_are_valid():
    for profile in sr.SCENARIO_PROFILES:
        values = sr.generate_scenario(profile, 99, _base())["values"]

        assert values["market_rent_growth_min"] <= values["market_rent_growth_max"]
        assert values["exit_cap_left"] <= values["exit_cap_mode"] <= values["exit_cap_right"]


def test_downside_is_directionally_weaker_than_base():
    base = _base()
    values = sr.generate_scenario("Downside", 42, base)["values"]

    assert values["initial_occupancy"] <= 0.83
    assert values["market_rent_growth_max"] <= base["market_rent_growth_max"]
    assert values["exit_cap_mode"] >= base["exit_cap_mode"]
    assert values["opex_growth_rate"] >= base["opex_growth_rate"]


def test_debt_stress_pressures_debt_assumptions():
    base = _base()
    values = sr.generate_scenario("Debt Stress", 42, base)["values"]

    assert values["interest_rate"] >= 0.08
    assert values["interest_rate"] > base["interest_rate"]
    assert values["debt_ratio"] >= 0.52
    assert values["refi_cost_rate"] >= base["refi_cost_rate"]


def test_lease_up_risk_weakens_leasing_assumptions():
    base = _base()
    values = sr.generate_scenario("Lease-Up Risk", 42, base)["values"]

    assert values["initial_occupancy"] <= 0.78
    assert values["renew_prob"] <= 0.50
    assert values["downtime_months"] >= base["downtime_months"]
    assert values["vacant_downtime_months"] >= base["vacant_downtime_months"]
    assert values["backfill_prob"] <= 0.90
    assert values["ti_psf_new"] >= base["ti_psf_new"]


def test_upside_remains_believable_and_in_bounds():
    values = sr.generate_scenario("Upside", 42, _base())["values"]

    assert 0.88 <= values["initial_occupancy"] <= 0.95
    assert values["market_rent_growth_max"] <= 0.07
    assert values["exit_cap_mode"] >= 0.075
    assert values["interest_rate"] >= 0.0575
    assert values["debt_ratio"] <= 0.55


def test_change_summary_contains_old_new_direction_and_reason():
    scenario = sr.generate_scenario("Conservative", 10, _base())
    summary = scenario["changes"]

    assert summary
    first = summary[0]
    assert {"field", "key", "old_value", "new_value", "direction", "reason"}.issubset(first)
    assert any(row["key"] == "initial_occupancy" for row in summary)


def test_validation_rejects_malformed_values():
    values = sr.generate_scenario("Base Variation", 100, _base())["values"]
    values["market_rent_growth_min"] = 0.06
    values["market_rent_growth_max"] = 0.02
    values["exit_cap_left"] = 0.10
    values["exit_cap_mode"] = 0.08
    values["initial_occupancy"] = float("nan")

    errors = sr.validate_generated_scenario(values)

    assert any("market_rent_growth_min" in error for error in errors)
    assert any("exit_cap_left" in error for error in errors)
    assert any("initial_occupancy must be finite" in error for error in errors)


def test_exit_cap_override_is_only_changed_when_currently_enabled():
    disabled = sr.generate_scenario("Downside", 8, _base())["values"]
    assert "exit_cap_override" not in disabled

    base = _base()
    base["exit_cap_override"] = 0.085
    enabled = sr.generate_scenario("Downside", 8, base)["values"]

    assert "exit_cap_override" in enabled
    assert enabled["exit_cap_override"] == enabled["exit_cap_mode"]
