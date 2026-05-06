from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from demo_presets import list_presets, load_preset
from export_contracts import (
    ContractValidationError,
    build_ai_context_export,
    build_business_summary_export,
    build_odoo_handoff_payload,
    validate_export_contract,
)
from risk_flags import generate_risk_flags
from scenario_matrix import build_27_case_matrix, build_scenario_matrix_export
from scenario_memo import render_scenario_review_memo
from scripts.generate_demo_bundle import generate_bundle


def test_export_contracts_validate_and_reject_missing_seed() -> None:
    df = _sample_df()
    flags = generate_risk_flags(df)
    business = build_business_summary_export(
        df,
        params={"market_rent_growth_min": 0.03},
        seed=123,
        preset="base",
        risk_flags=flags,
    )
    validate_export_contract("business_summary", business)

    ai_context = build_ai_context_export(business)
    odoo_payload = build_odoo_handoff_payload(business)
    validate_export_contract("ai_context", ai_context)
    validate_export_contract("odoo_handoff_payload", odoo_payload)
    assert odoo_payload["network_calls_made"] is False
    assert odoo_payload["proposed_odoo_target"]["live_integration"] is False

    broken = dict(business)
    broken.pop("seed")
    with pytest.raises(ContractValidationError):
        validate_export_contract("business_summary", broken)


def test_27_case_matrix_contract_and_probability_sum() -> None:
    matrix = build_27_case_matrix(
        base_params={},
        seed=77,
        sims_per_case=3,
        runner=_fake_runner,
    )
    export = build_scenario_matrix_export(matrix, seed=77, inputs={}, sims_per_case=3)
    validate_export_contract("scenario_matrix", export)

    assert len(matrix) == 27
    assert export["base_case_id"] == "S-BASE-BASE-BASE"
    assert any(row["scenario_id"] == "S-BASE-BASE-BASE" for row in matrix)
    assert abs(sum(row["probability"] for row in matrix) - 1.0) < 1e-12
    assert export["label"] == "demo_sensitivity_not_forecast_or_advice"


def test_risk_flags_cover_required_categories_without_advice_language() -> None:
    df = pd.DataFrame(
        {
            "IRR": [-0.25, -0.05, 0.02, 0.44, 0.55],
            "MinDSCR": [0.92, 1.05, 1.10, 1.12, 1.14],
            "MinDebtYield": [0.045, 0.055, 0.06, 0.065, 0.07],
            "LTV": [0.70, 0.72, 0.78, 0.74, 0.76],
            "NetCashFlow": [-1000, 50, 75, 100, 125],
            "NOI_Y1": [1, 1, 1, 1, 1],
        }
    )
    flags = generate_risk_flags(df)
    metrics = {flag["metric"] for flag in flags}
    messages = " ".join(flag["message"].lower() for flag in flags)

    assert {"DSCR", "DebtYield", "LTV", "IRR_P5", "NetCashFlow", "IRR_P95_P5_SPREAD"} <= metrics
    assert "buy" not in messages
    assert "sell" not in messages
    assert "recommend" not in messages


def test_memo_is_deterministic_and_has_no_verdict_language() -> None:
    df = _sample_df()
    flags = generate_risk_flags(df)
    business = build_business_summary_export(
        df,
        params={},
        seed=456,
        preset="base",
        risk_flags=flags,
    )
    matrix = build_27_case_matrix(base_params={}, seed=456, sims_per_case=2, runner=_fake_runner)
    memo_one = render_scenario_review_memo(
        business_summary=business,
        scenario_matrix=matrix,
        risk_flags=flags,
        manifest={"bundle_id": "base-456", "generated_files": ["a.json"]},
    )
    memo_two = render_scenario_review_memo(
        business_summary=business,
        scenario_matrix=matrix,
        risk_flags=flags,
        manifest={"bundle_id": "base-456", "generated_files": ["a.json"]},
    )

    lowered = memo_one.lower()
    assert memo_one == memo_two
    assert "scenario review memo" in lowered
    assert "strong_buy" not in lowered
    assert "pass / fail" not in lowered
    assert "recommendation" not in lowered


def test_demo_presets_are_available_and_well_formed() -> None:
    expected = {"base", "conservative", "upside", "downside", "debt-stress", "lease-up-risk"}
    assert expected <= set(list_presets())
    for preset in expected:
        payload = load_preset(preset)
        assert payload["name"] == preset
        assert isinstance(payload["params"], dict)


def test_generate_bundle_writes_reviewer_artifacts(tmp_path: Path) -> None:
    result = generate_bundle(
        preset="base",
        seed=999,
        out_dir=tmp_path,
        n=3,
        sims_per_case=2,
        simulation_runner=_fake_runner,
        matrix_runner=_fake_runner,
    )
    expected_files = {
        "inputs.json",
        "business_summary.json",
        "ai_context.json",
        "odoo_handoff_payload.json",
        "scenario_matrix.json",
        "scenario_matrix.csv",
        "risk_flags.json",
        "scenario_review_memo.md",
        "validation_report.json",
        "manifest.json",
    }
    assert expected_files <= {path.name for path in tmp_path.iterdir()}
    assert result["validation_report"]["all_valid"] is True

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 999
    assert manifest["network_calls_made"] is False
    assert manifest["tests_run"][0]["status"] == "not_run"

    matrix = json.loads((tmp_path / "scenario_matrix.json").read_text(encoding="utf-8"))
    assert len(matrix["matrix"]) == 27
    assert matrix["network_calls_made"] is False


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "IRR": [0.10, 0.12, 0.14, 0.16, 0.18],
            "NPV": [100, 200, 300, 400, 500],
            "CoC": [0.05, 0.06, 0.07, 0.08, 0.09],
            "EquityMultiple": [1.1, 1.2, 1.3, 1.4, 1.5],
            "MinDSCR": [1.20, 1.22, 1.24, 1.26, 1.28],
            "MinDebtYield": [0.07, 0.08, 0.09, 0.10, 0.11],
            "LTV": [0.50, 0.55, 0.60, 0.62, 0.64],
            "NOI_Y1": [10, 11, 12, 13, 14],
        }
    )


def _fake_runner(params: dict, n: int, seed: int) -> pd.DataFrame:
    rent = float(params.get("market_rent_growth_min", 0.03))
    expense = float(params.get("opex_growth_rate", 0.03))
    exit_cap = float(params.get("exit_cap_override", 0.085))
    base = 0.12 + rent * 1.5 - expense * 0.7 + (0.085 - exit_cap) * 2.0
    rows = []
    for idx in range(n):
        bump = (idx + 1) * 0.002 + (seed % 13) * 0.0001
        rows.append(
            {
                "IRR": base + bump,
                "NPV": 1_000_000 + 10_000 * idx + seed,
                "CoC": 0.06 + rent + bump / 5,
                "EquityMultiple": 1.2 + base + bump,
                "MinDSCR": 1.35 - max(expense - 0.03, 0) * 3,
                "MinDebtYield": 0.09 - max(expense - 0.03, 0),
                "LTV": 0.55 + max(exit_cap - 0.085, 0),
                "NOI_Y1": 100_000 + idx,
            }
        )
    return pd.DataFrame(rows)
