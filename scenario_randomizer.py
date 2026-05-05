from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any, Mapping


SCENARIO_PROFILES: tuple[str, ...] = (
    "Base Variation",
    "Conservative",
    "Upside",
    "Downside",
    "Debt Stress",
    "Lease-Up Risk",
    "Random Plausible",
)

CAVEAT = (
    "Generated scenarios are for demo/testing and sensitivity exploration only. "
    "They are not forecasts, investment advice, or validated market underwriting."
)

BASE_INPUTS: dict[str, Any] = {
    "in_place_rent_psf": 23.64,
    "initial_occupancy": 0.826,
    "market_rent_psf": 27.0,
    "purchase_price": 108_000_000,
    "market_rent_growth_min": 0.02,
    "market_rent_growth_max": 0.04,
    "rent_spread_std": 0.05,
    "renewal_spread_std": 0.01,
    "exit_cap_left": 0.075,
    "exit_cap_mode": 0.085,
    "exit_cap_right": 0.09,
    "exit_cap_override": None,
    "operating_expenses_start": 2_500_000,
    "opex_growth_rate": 0.03,
    "property_tax_rate": 0.015,
    "tax_growth_rate": 0.025,
    "walt_years": 7.0,
    "ti_psf_new": 60.0,
    "ti_psf_renew": 25.0,
    "lc_pct_new": 0.06,
    "lc_pct_renew": 0.06,
    "renew_prob": 0.60,
    "downtime_months": 6,
    "vacant_downtime_months": 3,
    "renew_free_months": None,
    "renew_downtime_months": None,
    "backfill_prob": 0.97,
    "frictional_vacancy_floor": 0.03,
    "in_term_bump_pct": 0.02,
    "debt_ratio": 0.45,
    "interest_rate": 0.0675,
    "refi_cost_rate": 0.025,
    "interest_only_years": 2,
    "amort_years": 25,
    "reserve_per_rsf": 0.25,
    "reserve_escalation": 0.03,
    "sale_cost_rate": 0.02,
    "discount_rate": 0.10,
    "acq_cost_rate": 0.015,
    "financing_fee_rate": 0.01,
    "rate_cap_cost": 0.015,
    "working_capital_reserve": 1_000_000,
    "contingency_reserve": 1_500_000,
}

FIELD_SPECS: dict[str, dict[str, Any]] = {
    "in_place_rent_psf": {"label": "In-place Rent", "kind": "currency_psf", "min": 10.0, "max": 60.0, "category": "rent assumption"},
    "initial_occupancy": {"label": "Initial Occupancy", "kind": "percent", "min": 0.65, "max": 0.98, "category": "occupancy"},
    "market_rent_psf": {"label": "Market Rent", "kind": "currency_psf", "min": 10.0, "max": 75.0, "category": "rent assumption"},
    "purchase_price": {"label": "Purchase Price", "kind": "currency", "min": 50_000_000, "max": 175_000_000, "category": "basis"},
    "market_rent_growth_min": {"label": "Rent Growth Min", "kind": "percent", "min": 0.0, "max": 0.07, "category": "growth"},
    "market_rent_growth_max": {"label": "Rent Growth Max", "kind": "percent", "min": 0.0, "max": 0.07, "category": "growth"},
    "rent_spread_std": {"label": "Rent Spread Std", "kind": "percent", "min": 0.01, "max": 0.09, "category": "rent volatility"},
    "renewal_spread_std": {"label": "Renewal Spread Std", "kind": "percent", "min": 0.005, "max": 0.04, "category": "renewal volatility"},
    "exit_cap_left": {"label": "Exit Cap Left", "kind": "percent", "min": 0.065, "max": 0.105, "category": "exit valuation"},
    "exit_cap_mode": {"label": "Exit Cap Mode", "kind": "percent", "min": 0.065, "max": 0.105, "category": "exit valuation"},
    "exit_cap_right": {"label": "Exit Cap Right", "kind": "percent", "min": 0.065, "max": 0.105, "category": "exit valuation"},
    "exit_cap_override": {"label": "Exit Cap Override", "kind": "percent_optional", "min": 0.05, "max": 0.15, "category": "exit valuation"},
    "operating_expenses_start": {"label": "Operating Expenses Start", "kind": "currency", "min": 1_000_000, "max": 6_000_000, "category": "expense"},
    "opex_growth_rate": {"label": "OPEX Growth", "kind": "percent", "min": 0.02, "max": 0.06, "category": "expense"},
    "property_tax_rate": {"label": "Property Tax Rate", "kind": "percent", "min": 0.01, "max": 0.025, "category": "tax"},
    "tax_growth_rate": {"label": "Tax Growth Rate", "kind": "percent", "min": 0.015, "max": 0.05, "category": "tax"},
    "walt_years": {"label": "WALT", "kind": "years", "min": 4.0, "max": 9.0, "category": "lease term"},
    "ti_psf_new": {"label": "TI Cost - New", "kind": "currency_psf", "min": 40.0, "max": 100.0, "category": "leasing cost"},
    "ti_psf_renew": {"label": "TI Cost - Renewal", "kind": "currency_psf", "min": 15.0, "max": 50.0, "category": "leasing cost"},
    "lc_pct_new": {"label": "LC New", "kind": "percent", "min": 0.04, "max": 0.085, "category": "leasing cost"},
    "lc_pct_renew": {"label": "LC Renewal", "kind": "percent", "min": 0.04, "max": 0.085, "category": "leasing cost"},
    "renew_prob": {"label": "Renewal Probability", "kind": "percent", "min": 0.30, "max": 0.85, "category": "leasing probability"},
    "downtime_months": {"label": "Downtime - New", "kind": "months", "min": 0, "max": 14, "category": "lease-up"},
    "vacant_downtime_months": {"label": "Downtime - Vacant", "kind": "months", "min": 0, "max": 14, "category": "lease-up"},
    "renew_free_months": {"label": "Renewal Free Months", "kind": "months_optional", "min": 0, "max": 12, "category": "lease-up"},
    "renew_downtime_months": {"label": "Renewal Downtime", "kind": "months_optional", "min": 0, "max": 12, "category": "lease-up"},
    "backfill_prob": {"label": "Backfill Probability", "kind": "percent", "min": 0.75, "max": 0.99, "category": "lease-up"},
    "frictional_vacancy_floor": {"label": "Frictional Vacancy Floor", "kind": "percent", "min": 0.02, "max": 0.09, "category": "occupancy"},
    "in_term_bump_pct": {"label": "In-Term Bump", "kind": "percent", "min": 0.005, "max": 0.04, "category": "rent growth"},
    "debt_ratio": {"label": "Debt Ratio", "kind": "percent", "min": 0.30, "max": 0.70, "category": "leverage"},
    "interest_rate": {"label": "Interest Rate", "kind": "percent", "min": 0.04, "max": 0.10, "category": "debt cost"},
    "refi_cost_rate": {"label": "Refi Cost Rate", "kind": "percent", "min": 0.01, "max": 0.05, "category": "financing cost"},
    "interest_only_years": {"label": "Interest Only Years", "kind": "years_int", "min": 0, "max": 5, "category": "debt structure"},
    "amort_years": {"label": "Amortization Years", "kind": "years_int", "min": 20, "max": 30, "category": "debt structure"},
    "reserve_per_rsf": {"label": "Reserve per RSF", "kind": "currency_psf", "min": 0.10, "max": 0.75, "category": "reserve"},
    "reserve_escalation": {"label": "Reserve Escalation", "kind": "percent", "min": 0.015, "max": 0.06, "category": "reserve"},
    "sale_cost_rate": {"label": "Sale Cost Rate", "kind": "percent", "min": 0.01, "max": 0.04, "category": "sale cost"},
    "discount_rate": {"label": "Discount Rate", "kind": "percent", "min": 0.085, "max": 0.13, "category": "valuation"},
    "acq_cost_rate": {"label": "Acquisition Cost Rate", "kind": "percent", "min": 0.005, "max": 0.03, "category": "transaction cost"},
    "financing_fee_rate": {"label": "Financing Fee Rate", "kind": "percent", "min": 0.005, "max": 0.03, "category": "financing cost"},
    "rate_cap_cost": {"label": "Rate Cap Cost", "kind": "percent", "min": 0.005, "max": 0.04, "category": "financing cost"},
    "working_capital_reserve": {"label": "Working Capital Reserve", "kind": "currency", "min": 250_000, "max": 3_000_000, "category": "reserve"},
    "contingency_reserve": {"label": "Contingency Reserve", "kind": "currency", "min": 500_000, "max": 3_500_000, "category": "reserve"},
}

RANDOMIZABLE_FIELDS: tuple[str, ...] = tuple(
    key for key in FIELD_SPECS if key != "exit_cap_override"
)


def extract_current_inputs(mapping: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in BASE_INPUTS:
        default = deepcopy(BASE_INPUTS[key])
        raw = mapping.get(key, default) if hasattr(mapping, "get") else default
        if raw is None and key != "exit_cap_override":
            raw = default
        values[key] = deepcopy(raw)
    return values


def base_reset_inputs() -> dict[str, Any]:
    return deepcopy(BASE_INPUTS)


def generate_scenario(profile: str, seed: int, current_inputs: Mapping[str, Any]) -> dict[str, Any]:
    if profile not in SCENARIO_PROFILES:
        raise ValueError(f"Unknown scenario profile: {profile}")

    rng = random.Random(f"{profile}:{int(seed)}")
    current = extract_current_inputs(current_inputs)
    resolved_profile = profile
    if profile == "Random Plausible":
        resolved_profile = rng.choice(
            [
                "Base Variation",
                "Conservative",
                "Upside",
                "Downside",
                "Debt Stress",
                "Lease-Up Risk",
            ]
        )

    values = _generate_values_for_profile(resolved_profile, rng, current)
    if current.get("exit_cap_override") is not None:
        values["exit_cap_override"] = _round_rate(values["exit_cap_mode"])

    errors = validate_generated_scenario(values)
    if errors:
        raise ValueError("; ".join(errors))

    changes = build_change_summary(current, values)
    return {
        "profile": profile,
        "resolved_profile": resolved_profile,
        "seed": int(seed),
        "values": values,
        "changes": changes,
        "caveat": CAVEAT,
    }


def validate_generated_scenario(values: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, spec in FIELD_SPECS.items():
        if key not in values:
            if key == "exit_cap_override":
                continue
            errors.append(f"{key} is missing")
            continue
        value = values[key]
        if value is None:
            if key == "exit_cap_override":
                continue
            errors.append(f"{key} is None")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{key} must be numeric")
            continue
        if not math.isfinite(float(value)):
            errors.append(f"{key} must be finite")
            continue
        if float(value) < float(spec["min"]) or float(value) > float(spec["max"]):
            errors.append(f"{key}={value} outside {spec['min']}..{spec['max']}")

    gmin = float(values.get("market_rent_growth_min", math.nan))
    gmax = float(values.get("market_rent_growth_max", math.nan))
    if math.isfinite(gmin) and math.isfinite(gmax) and gmin > gmax:
        errors.append("market_rent_growth_min must be <= market_rent_growth_max")

    left = float(values.get("exit_cap_left", math.nan))
    mode = float(values.get("exit_cap_mode", math.nan))
    right = float(values.get("exit_cap_right", math.nan))
    if all(math.isfinite(v) for v in (left, mode, right)) and not (left <= mode <= right):
        errors.append("exit_cap_left <= exit_cap_mode <= exit_cap_right is required")

    in_place = float(values.get("in_place_rent_psf", math.nan))
    market = float(values.get("market_rent_psf", math.nan))
    if math.isfinite(in_place) and math.isfinite(market) and in_place > 0:
        ratio = market / in_place
        if ratio < 0.85 or ratio > 1.35:
            errors.append("market_rent_psf must stay reasonably related to in_place_rent_psf")

    return errors


def build_change_summary(
    old_inputs: Mapping[str, Any],
    new_inputs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    old = extract_current_inputs(old_inputs)
    rows: list[dict[str, Any]] = []
    for key in RANDOMIZABLE_FIELDS + ("exit_cap_override",):
        if key not in new_inputs:
            continue
        old_value = old.get(key)
        new_value = new_inputs.get(key)
        if _equivalent(old_value, new_value):
            continue
        spec = FIELD_SPECS[key]
        rows.append(
            {
                "field": spec["label"],
                "key": key,
                "old_value": _format_value(old_value, spec["kind"]),
                "new_value": _format_value(new_value, spec["kind"]),
                "direction": _direction_for_change(key, old_value, new_value),
                "reason": spec["category"],
            }
        )
    return rows


def _generate_values_for_profile(
    profile: str,
    rng: random.Random,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    if profile == "Base Variation":
        values = _base_variation(rng, current)
    else:
        ranges = _profile_ranges(profile)
        values = {
            "in_place_rent_psf": _round_money_psf(_uniform(rng, *ranges["in_place_rent_psf"])),
            "initial_occupancy": _round_rate(_uniform(rng, *ranges["initial_occupancy"])),
            "purchase_price": _round_dollars(_uniform(rng, *ranges["purchase_price"])),
            "market_rent_growth_min": _round_rate(_uniform(rng, *ranges["growth_min"])),
            "rent_spread_std": _round_rate(_uniform(rng, *ranges["rent_spread_std"])),
            "renewal_spread_std": _round_rate(_uniform(rng, *ranges["renewal_spread_std"])),
            "operating_expenses_start": _round_dollars(_uniform(rng, *ranges["operating_expenses_start"])),
            "opex_growth_rate": _round_rate(_uniform(rng, *ranges["opex_growth_rate"])),
            "property_tax_rate": _round_rate(_uniform(rng, *ranges["property_tax_rate"])),
            "tax_growth_rate": _round_rate(_uniform(rng, *ranges["tax_growth_rate"])),
            "walt_years": _round_half(_uniform(rng, *ranges["walt_years"])),
            "ti_psf_new": _round_money_psf(_uniform(rng, *ranges["ti_psf_new"]), step=5.0),
            "ti_psf_renew": _round_money_psf(_uniform(rng, *ranges["ti_psf_renew"]), step=5.0),
            "lc_pct_new": _round_rate(_uniform(rng, *ranges["lc_pct_new"])),
            "lc_pct_renew": _round_rate(_uniform(rng, *ranges["lc_pct_renew"])),
            "renew_prob": _round_rate(_uniform(rng, *ranges["renew_prob"])),
            "downtime_months": _rand_int(rng, *ranges["downtime_months"]),
            "vacant_downtime_months": _rand_int(rng, *ranges["vacant_downtime_months"]),
            "renew_free_months": _rand_int(rng, *ranges["renew_free_months"]),
            "renew_downtime_months": _rand_int(rng, *ranges["renew_downtime_months"]),
            "backfill_prob": _round_rate(_uniform(rng, *ranges["backfill_prob"])),
            "frictional_vacancy_floor": _round_rate(_uniform(rng, *ranges["frictional_vacancy_floor"])),
            "in_term_bump_pct": _round_rate(_uniform(rng, *ranges["in_term_bump_pct"])),
            "debt_ratio": _round_rate(_uniform(rng, *ranges["debt_ratio"])),
            "interest_rate": _round_rate(_uniform(rng, *ranges["interest_rate"])),
            "refi_cost_rate": _round_rate(_uniform(rng, *ranges["refi_cost_rate"])),
            "interest_only_years": _rand_int(rng, *ranges["interest_only_years"]),
            "amort_years": _rand_int(rng, *ranges["amort_years"]),
            "reserve_per_rsf": _round_money_psf(_uniform(rng, *ranges["reserve_per_rsf"]), step=0.05),
            "reserve_escalation": _round_rate(_uniform(rng, *ranges["reserve_escalation"])),
            "sale_cost_rate": _round_rate(_uniform(rng, *ranges["sale_cost_rate"])),
            "discount_rate": _round_rate(_uniform(rng, *ranges["discount_rate"])),
            "acq_cost_rate": _round_rate(_uniform(rng, *ranges["acq_cost_rate"])),
            "financing_fee_rate": _round_rate(_uniform(rng, *ranges["financing_fee_rate"])),
            "rate_cap_cost": _round_rate(_uniform(rng, *ranges["rate_cap_cost"])),
            "working_capital_reserve": _round_dollars(_uniform(rng, *ranges["working_capital_reserve"]), step=50_000),
            "contingency_reserve": _round_dollars(_uniform(rng, *ranges["contingency_reserve"]), step=50_000),
        }
        values["market_rent_growth_max"] = _round_rate(
            min(0.07, max(values["market_rent_growth_min"], values["market_rent_growth_min"] + _uniform(rng, *ranges["growth_spread"])))
        )
        values.update(_exit_cap_band(rng, ranges["exit_cap_mode"]))
        values["market_rent_psf"] = _round_money_psf(
            _clamp(
                values["in_place_rent_psf"] * _uniform(rng, *ranges["market_to_in_place"]),
                FIELD_SPECS["market_rent_psf"]["min"],
                FIELD_SPECS["market_rent_psf"]["max"],
            )
        )

    return {key: _coerce_to_spec(key, value) for key, value in values.items()}


def _profile_ranges(profile: str) -> dict[str, tuple[float, float]]:
    common = {
        "rent_spread_std": (0.025, 0.065),
        "renewal_spread_std": (0.005, 0.025),
        "property_tax_rate": (0.012, 0.021),
        "tax_growth_rate": (0.020, 0.040),
        "walt_years": (5.0, 8.0),
        "renew_free_months": (0, 4),
        "renew_downtime_months": (0, 3),
        "refi_cost_rate": (0.015, 0.035),
        "amort_years": (22, 30),
        "reserve_escalation": (0.020, 0.045),
        "sale_cost_rate": (0.015, 0.030),
        "acq_cost_rate": (0.010, 0.022),
        "working_capital_reserve": (500_000, 2_000_000),
        "contingency_reserve": (750_000, 2_500_000),
    }
    profiles: dict[str, dict[str, tuple[float, float]]] = {
        "Conservative": {
            "in_place_rent_psf": (22.0, 25.0),
            "initial_occupancy": (0.78, 0.88),
            "purchase_price": (105_000_000, 114_000_000),
            "growth_min": (0.010, 0.020),
            "growth_spread": (0.005, 0.012),
            "exit_cap_mode": (0.085, 0.095),
            "market_to_in_place": (1.05, 1.16),
            "operating_expenses_start": (2_600_000, 3_050_000),
            "opex_growth_rate": (0.030, 0.050),
            "ti_psf_new": (55.0, 80.0),
            "ti_psf_renew": (25.0, 40.0),
            "lc_pct_new": (0.055, 0.075),
            "lc_pct_renew": (0.050, 0.070),
            "renew_prob": (0.50, 0.65),
            "downtime_months": (5, 9),
            "vacant_downtime_months": (4, 8),
            "backfill_prob": (0.88, 0.96),
            "frictional_vacancy_floor": (0.035, 0.060),
            "in_term_bump_pct": (0.015, 0.028),
            "debt_ratio": (0.35, 0.45),
            "interest_rate": (0.0675, 0.0825),
            "interest_only_years": (1, 2),
            "reserve_per_rsf": (0.25, 0.45),
            "discount_rate": (0.100, 0.120),
            "financing_fee_rate": (0.010, 0.020),
            "rate_cap_cost": (0.012, 0.030),
        },
        "Upside": {
            "in_place_rent_psf": (23.5, 26.0),
            "initial_occupancy": (0.88, 0.95),
            "purchase_price": (102_000_000, 110_000_000),
            "growth_min": (0.030, 0.042),
            "growth_spread": (0.006, 0.012),
            "exit_cap_mode": (0.075, 0.085),
            "market_to_in_place": (1.10, 1.22),
            "operating_expenses_start": (2_250_000, 2_600_000),
            "opex_growth_rate": (0.020, 0.035),
            "ti_psf_new": (40.0, 65.0),
            "ti_psf_renew": (15.0, 30.0),
            "lc_pct_new": (0.040, 0.060),
            "lc_pct_renew": (0.040, 0.055),
            "renew_prob": (0.65, 0.80),
            "downtime_months": (2, 6),
            "vacant_downtime_months": (1, 4),
            "backfill_prob": (0.94, 0.99),
            "frictional_vacancy_floor": (0.020, 0.040),
            "in_term_bump_pct": (0.020, 0.035),
            "debt_ratio": (0.45, 0.55),
            "interest_rate": (0.0575, 0.0675),
            "interest_only_years": (2, 3),
            "reserve_per_rsf": (0.10, 0.30),
            "discount_rate": (0.085, 0.105),
            "financing_fee_rate": (0.005, 0.015),
            "rate_cap_cost": (0.005, 0.020),
        },
        "Downside": {
            "in_place_rent_psf": (21.5, 24.0),
            "initial_occupancy": (0.70, 0.83),
            "purchase_price": (108_000_000, 116_000_000),
            "growth_min": (0.000, 0.012),
            "growth_spread": (0.004, 0.010),
            "exit_cap_mode": (0.090, 0.1025),
            "market_to_in_place": (1.00, 1.12),
            "operating_expenses_start": (2_750_000, 3_300_000),
            "opex_growth_rate": (0.040, 0.060),
            "ti_psf_new": (65.0, 95.0),
            "ti_psf_renew": (30.0, 50.0),
            "lc_pct_new": (0.060, 0.085),
            "lc_pct_renew": (0.055, 0.080),
            "renew_prob": (0.40, 0.58),
            "downtime_months": (7, 12),
            "vacant_downtime_months": (6, 11),
            "backfill_prob": (0.78, 0.92),
            "frictional_vacancy_floor": (0.050, 0.085),
            "in_term_bump_pct": (0.005, 0.018),
            "debt_ratio": (0.40, 0.52),
            "interest_rate": (0.070, 0.090),
            "interest_only_years": (0, 2),
            "reserve_per_rsf": (0.35, 0.65),
            "discount_rate": (0.110, 0.130),
            "financing_fee_rate": (0.015, 0.030),
            "rate_cap_cost": (0.020, 0.040),
        },
        "Debt Stress": {
            "in_place_rent_psf": (22.5, 25.0),
            "initial_occupancy": (0.78, 0.88),
            "purchase_price": (105_000_000, 114_000_000),
            "growth_min": (0.010, 0.030),
            "growth_spread": (0.004, 0.012),
            "exit_cap_mode": (0.085, 0.095),
            "market_to_in_place": (1.04, 1.16),
            "operating_expenses_start": (2_550_000, 3_050_000),
            "opex_growth_rate": (0.030, 0.050),
            "ti_psf_new": (55.0, 80.0),
            "ti_psf_renew": (25.0, 40.0),
            "lc_pct_new": (0.055, 0.075),
            "lc_pct_renew": (0.050, 0.070),
            "renew_prob": (0.48, 0.65),
            "downtime_months": (5, 9),
            "vacant_downtime_months": (4, 8),
            "backfill_prob": (0.84, 0.95),
            "frictional_vacancy_floor": (0.040, 0.070),
            "in_term_bump_pct": (0.012, 0.025),
            "debt_ratio": (0.52, 0.60),
            "interest_rate": (0.080, 0.100),
            "interest_only_years": (0, 2),
            "refi_cost_rate": (0.030, 0.050),
            "reserve_per_rsf": (0.25, 0.55),
            "discount_rate": (0.105, 0.130),
            "financing_fee_rate": (0.018, 0.030),
            "rate_cap_cost": (0.025, 0.040),
        },
        "Lease-Up Risk": {
            "in_place_rent_psf": (21.5, 24.5),
            "initial_occupancy": (0.65, 0.78),
            "purchase_price": (104_000_000, 113_000_000),
            "growth_min": (0.005, 0.025),
            "growth_spread": (0.004, 0.012),
            "exit_cap_mode": (0.085, 0.0975),
            "market_to_in_place": (1.02, 1.16),
            "operating_expenses_start": (2_600_000, 3_150_000),
            "opex_growth_rate": (0.030, 0.055),
            "ti_psf_new": (70.0, 100.0),
            "ti_psf_renew": (30.0, 50.0),
            "lc_pct_new": (0.065, 0.085),
            "lc_pct_renew": (0.055, 0.080),
            "renew_prob": (0.35, 0.50),
            "downtime_months": (8, 14),
            "vacant_downtime_months": (6, 12),
            "renew_free_months": (3, 8),
            "renew_downtime_months": (1, 5),
            "backfill_prob": (0.75, 0.90),
            "frictional_vacancy_floor": (0.050, 0.090),
            "in_term_bump_pct": (0.008, 0.022),
            "debt_ratio": (0.38, 0.50),
            "interest_rate": (0.0675, 0.085),
            "interest_only_years": (0, 2),
            "reserve_per_rsf": (0.30, 0.60),
            "discount_rate": (0.105, 0.130),
            "financing_fee_rate": (0.012, 0.025),
            "rate_cap_cost": (0.015, 0.035),
        },
    }
    selected = {**common, **profiles[profile]}
    selected.setdefault("refi_cost_rate", common["refi_cost_rate"])
    return selected


def _base_variation(rng: random.Random, current: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in RANDOMIZABLE_FIELDS:
        spec = FIELD_SPECS[key]
        old = current.get(key, BASE_INPUTS[key])
        if old is None:
            old = 0 if spec["kind"] in {"months_optional"} else BASE_INPUTS[key]
        if spec["kind"] in {"months", "months_optional", "years_int"}:
            spread = 1 if key != "amort_years" else 2
            values[key] = _rand_int(
                rng,
                max(int(spec["min"]), int(old) - spread),
                min(int(spec["max"]), int(old) + spread),
            )
        elif spec["kind"] == "currency":
            values[key] = _round_dollars(_jitter(rng, float(old), 0.06, spec), step=50_000)
        elif spec["kind"] == "currency_psf":
            step = 5.0 if key.startswith("ti_") else 0.25
            values[key] = _round_money_psf(_jitter(rng, float(old), 0.06, spec), step=step)
        elif spec["kind"] == "years":
            values[key] = _round_half(_jitter(rng, float(old), 0.08, spec))
        else:
            values[key] = _round_rate(_jitter(rng, float(old), 0.12, spec))

    if values["market_rent_growth_min"] > values["market_rent_growth_max"]:
        values["market_rent_growth_min"], values["market_rent_growth_max"] = (
            values["market_rent_growth_max"],
            values["market_rent_growth_min"],
        )
    if values["exit_cap_left"] > values["exit_cap_mode"]:
        values["exit_cap_left"] = max(0.065, values["exit_cap_mode"] - 0.005)
    if values["exit_cap_mode"] > values["exit_cap_right"]:
        values["exit_cap_right"] = min(0.105, values["exit_cap_mode"] + 0.005)

    values["market_rent_psf"] = _round_money_psf(
        _clamp(
            values["market_rent_psf"],
            max(10.0, values["in_place_rent_psf"] * 0.90),
            min(75.0, values["in_place_rent_psf"] * 1.30),
        )
    )
    return values


def _exit_cap_band(rng: random.Random, mode_range: tuple[float, float]) -> dict[str, float]:
    mode = _round_rate(_uniform(rng, *mode_range))
    left = _round_rate(max(0.065, mode - _uniform(rng, 0.004, 0.009)))
    right = _round_rate(min(0.105, mode + _uniform(rng, 0.004, 0.012)))
    if left > mode:
        left = mode
    if right < mode:
        right = mode
    return {"exit_cap_left": left, "exit_cap_mode": mode, "exit_cap_right": right}


def _coerce_to_spec(key: str, value: Any) -> Any:
    spec = FIELD_SPECS[key]
    if value is None:
        return None
    if spec["kind"] in {"months", "months_optional", "years_int"}:
        return int(_clamp(int(value), spec["min"], spec["max"]))
    if spec["kind"] == "currency":
        return int(_clamp(float(value), spec["min"], spec["max"]))
    return float(_clamp(float(value), spec["min"], spec["max"]))


def _direction_for_change(key: str, old_value: Any, new_value: Any) -> str:
    if old_value is None:
        return "sets explicit assumption"
    try:
        old = float(old_value)
        new = float(new_value)
    except Exception:
        return "changed assumption"
    if abs(new - old) < 1e-9:
        return "unchanged"
    higher = new > old
    if key in {"initial_occupancy", "market_rent_growth_min", "market_rent_growth_max", "renew_prob", "backfill_prob", "in_term_bump_pct", "walt_years"}:
        return "stronger assumption" if higher else "weaker assumption"
    if key in {"exit_cap_left", "exit_cap_mode", "exit_cap_right", "interest_rate", "opex_growth_rate", "property_tax_rate", "tax_growth_rate", "ti_psf_new", "ti_psf_renew", "lc_pct_new", "lc_pct_renew", "downtime_months", "vacant_downtime_months", "renew_free_months", "renew_downtime_months", "frictional_vacancy_floor", "refi_cost_rate", "sale_cost_rate", "discount_rate", "acq_cost_rate", "financing_fee_rate", "rate_cap_cost", "operating_expenses_start", "reserve_per_rsf", "reserve_escalation", "working_capital_reserve", "contingency_reserve"}:
        return "more conservative / higher cost" if higher else "less conservative / lower cost"
    if key == "debt_ratio":
        return "higher leverage" if higher else "lower leverage"
    if key == "purchase_price":
        return "higher basis" if higher else "lower basis"
    return "increased" if higher else "decreased"


def _format_value(value: Any, kind: str) -> str:
    if value is None:
        return "not set"
    if kind in {"percent", "percent_optional"}:
        return f"{float(value):.1%}"
    if kind == "currency":
        amount = float(value)
        if abs(amount) >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        return f"${amount:,.0f}"
    if kind == "currency_psf":
        return f"${float(value):,.2f}"
    if kind in {"months", "months_optional"}:
        return f"{int(value)} mo"
    if kind in {"years", "years_int"}:
        return f"{float(value):.1f} yr" if kind == "years" else f"{int(value)} yr"
    return str(value)


def _equivalent(old_value: Any, new_value: Any) -> bool:
    if old_value is None or new_value is None:
        return old_value is None and new_value is None
    try:
        return abs(float(old_value) - float(new_value)) < 1e-9
    except Exception:
        return old_value == new_value


def _jitter(rng: random.Random, value: float, pct: float, spec: Mapping[str, Any]) -> float:
    low = max(float(spec["min"]), value * (1.0 - pct))
    high = min(float(spec["max"]), value * (1.0 + pct))
    if low > high:
        low, high = float(spec["min"]), float(spec["max"])
    return _uniform(rng, low, high)


def _uniform(rng: random.Random, low: float, high: float) -> float:
    return float(rng.uniform(float(low), float(high)))


def _rand_int(rng: random.Random, low: float, high: float) -> int:
    return int(rng.randint(int(low), int(high)))


def _round_rate(value: float) -> float:
    return round(float(value), 4)


def _round_money_psf(value: float, step: float = 0.25) -> float:
    return round(round(float(value) / step) * step, 2)


def _round_dollars(value: float, step: int = 100_000) -> int:
    return int(round(float(value) / step) * step)


def _round_half(value: float) -> float:
    return round(float(value) * 2.0) / 2.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))
