from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api_app
from run_registry import fetch_bundle_run, record_bundle_run
from scripts.generate_demo_bundle import generate_bundle


def test_evidence_bundle_workflow_contract_is_valid_and_safe(tmp_path: Path) -> None:
    out_dir = tmp_path / "bundle"

    result = generate_bundle(
        preset="base",
        seed=123,
        out_dir=out_dir,
        n=3,
        sims_per_case=1,
        simulation_runner=_fake_runner,
        matrix_runner=_fake_runner,
    )

    assert result["validation_report"]["all_valid"] is True
    assert result["validation_report"]["network_calls_made"] is False
    assert "manifest.json" in result["generated_files"]
    assert all((out_dir / filename).exists() for filename in result["generated_files"])

    for filename in (
        "inputs.json",
        "business_summary.json",
        "ai_context.json",
        "odoo_handoff_payload.json",
        "scenario_matrix.json",
        "risk_flags.json",
        "validation_report.json",
        "manifest.json",
    ):
        payload = json.loads((out_dir / filename).read_text(encoding="utf-8"))
        assert payload.get("network_calls_made") is False

    scenario_matrix = json.loads((out_dir / "scenario_matrix.json").read_text(encoding="utf-8"))
    cases = scenario_matrix["matrix"]
    assert len(cases) == 27
    assert sum(case["probability"] for case in cases) == pytest.approx(1.0)
    assert any(case["scenario_id"] == scenario_matrix["base_case_id"] for case in cases)

    risk_flags = json.loads((out_dir / "risk_flags.json").read_text(encoding="utf-8"))
    for flag in risk_flags["flags"]:
        assert set(flag) >= {
            "severity",
            "category",
            "message",
            "metric",
            "threshold",
            "observed_value",
            "evidence_source",
        }
        assert "buy" not in flag["message"].lower()
        assert "sell" not in flag["message"].lower()

    memo = (out_dir / "scenario_review_memo.md").read_text(encoding="utf-8").lower()
    assert "scenario review memo" in memo
    assert "not investment advice" in memo
    assert "buy/sell" not in memo
    assert "strong_buy" not in memo


def test_registry_fetch_contract_returns_successful_runs_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "bundle"
    result = generate_bundle(
        preset="base",
        seed=123,
        out_dir=out_dir,
        n=3,
        sims_per_case=1,
        simulation_runner=_fake_runner,
        matrix_runner=_fake_runner,
    )
    db_path = tmp_path / "registry.sqlite"

    registry = record_bundle_run(db_path, result)
    row = fetch_bundle_run(db_path, registry["run_id"])

    assert row is not None
    assert row["run_id"] == registry["run_id"]
    assert row["preset"] == "base"
    assert row["seed"] == 123
    assert row["network_calls_made"] == 0
    assert json.loads(row["generated_files_json"]) == sorted(result["generated_files"])
    assert fetch_bundle_run(db_path, "missing-run") is None
    assert fetch_bundle_run(tmp_path / "missing.sqlite", registry["run_id"]) is None


def test_fastapi_workflow_contract_uses_registry_and_expected_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    monkeypatch.setattr(api_app, "generate_bundle", _fake_generate_bundle)
    client = TestClient(api_app.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["network_calls_made"] is False

    run_response = client.post(
        "/run-bundle",
        json={"preset": "base", "seed": 123, "n": 2, "sims_per_case": 1},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["validation_report_all_valid"] is True
    assert run_payload["network_calls_made"] is False
    assert set(run_payload["artifact_endpoints"]) == {"bundle", "risk_flags", "memo"}

    assert client.get(f"/bundle/{run_id}").status_code == 200
    assert client.get(f"/risk-flags/{run_id}").status_code == 200
    assert client.get(f"/memo/{run_id}").status_code == 200
    assert client.get("/bundle/not-a-real-run-id").status_code == 404


def _fake_generate_bundle(
    *,
    preset: str,
    seed: int,
    out_dir: Path,
    n: int,
    sims_per_case: int,
) -> dict[str, Any]:
    result = _fake_bundle_result(out_dir=out_dir, preset=preset, seed=seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(result["manifest"]), encoding="utf-8")
    (out_dir / "validation_report.json").write_text(
        json.dumps(result["validation_report"]),
        encoding="utf-8",
    )
    (out_dir / "risk_flags.json").write_text(
        json.dumps({"contract_name": "risk_flags", "flags": [], "network_calls_made": False}),
        encoding="utf-8",
    )
    (out_dir / "scenario_review_memo.md").write_text("# Scenario Review Memo\n", encoding="utf-8")
    return result


def _fake_bundle_result(*, out_dir: Path, preset: str, seed: int) -> dict[str, Any]:
    generated_at = "2026-05-07T00:00:00Z"
    generated_files = [
        "manifest.json",
        "validation_report.json",
        "risk_flags.json",
        "scenario_review_memo.md",
    ]
    manifest = {
        "bundle_id": f"{preset}-{seed}",
        "generated_at_utc": generated_at,
        "generated_files": generated_files,
        "network_calls_made": False,
        "output_dir": str(out_dir),
        "preset": preset,
        "repo_commit": "abc1234",
        "seed": seed,
    }
    validation_report = {
        "all_valid": True,
        "generated_at_utc": generated_at,
        "network_calls_made": False,
        "preset": preset,
        "seed": seed,
    }
    return {
        "bundle_dir": str(out_dir),
        "manifest": manifest,
        "validation_report": validation_report,
        "generated_files": sorted(generated_files),
    }


def _fake_runner(params: dict[str, Any], n: int, seed: int) -> pd.DataFrame:
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
