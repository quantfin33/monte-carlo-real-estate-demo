from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api_app
from run_registry import RUN_REGISTRY_TABLE
from scripts import generate_demo_bundle as bundle_cli


def test_health_returns_ok() -> None:
    client = TestClient(api_app.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rmc-evidence-api",
        "network_calls_made": False,
    }


def test_run_bundle_records_registry_and_exposes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    monkeypatch.setattr(api_app, "generate_bundle", _fake_generate_bundle)
    client = TestClient(api_app.app)

    response = client.post(
        "/run-bundle",
        json={"preset": "base", "seed": 123, "n": 2, "sims_per_case": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    run_id = payload["run_id"]
    assert run_id
    assert payload["validation_report_all_valid"] is True
    assert payload["validation_report"]["all_valid"] is True
    assert payload["network_calls_made"] is False
    assert payload["generated_files"] == sorted(_GENERATED_FILES)
    assert payload["artifact_endpoints"] == {
        "bundle": f"/bundle/{run_id}",
        "risk_flags": f"/risk-flags/{run_id}",
        "memo": f"/memo/{run_id}",
    }

    rows = _registry_rows(tmp_path / "registry.sqlite")
    assert len(rows) == 1
    assert rows[0]["run_id"] == run_id
    assert rows[0]["network_calls_made"] == 0

    bundle_response = client.get(f"/bundle/{run_id}")
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()
    assert bundle["registry"]["run_id"] == run_id
    assert bundle["registry"]["generated_files"] == sorted(_GENERATED_FILES)
    assert bundle["manifest"]["seed"] == 123
    assert bundle["validation_report"]["all_valid"] is True
    assert bundle["network_calls_made"] is False

    risk_response = client.get(f"/risk-flags/{run_id}")
    assert risk_response.status_code == 200
    assert risk_response.json()["contract_name"] == "risk_flags"

    memo_response = client.get(f"/memo/{run_id}")
    assert memo_response.status_code == 200
    assert "Scenario Review Memo" in memo_response.text


def test_unknown_run_id_returns_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    client = TestClient(api_app.app)

    assert client.get("/bundle/missing").status_code == 404
    assert client.get("/risk-flags/missing").status_code == 404
    assert client.get("/memo/missing").status_code == 404


def test_invalid_preset_returns_safe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    client = TestClient(api_app.app)

    response = client.post(
        "/run-bundle",
        json={"preset": "../base", "seed": 123, "n": 2, "sims_per_case": 1},
    )

    assert response.status_code == 400


def test_invalid_numeric_bounds_return_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    client = TestClient(api_app.app)

    response = client.post(
        "/run-bundle",
        json={"preset": "base", "seed": 123, "n": 0, "sims_per_case": 1},
    )

    assert response.status_code == 422


def test_request_rejects_arbitrary_output_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMC_API_BUNDLE_ROOT", str(tmp_path / "bundles"))
    monkeypatch.setenv("RMC_API_REGISTRY_DB", str(tmp_path / "registry.sqlite"))
    client = TestClient(api_app.app)

    response = client.post(
        "/run-bundle",
        json={
            "preset": "base",
            "seed": 123,
            "n": 2,
            "sims_per_case": 1,
            "out_dir": "/tmp/not-allowed",
        },
    )

    assert response.status_code == 422


def test_cli_without_registry_flag_remains_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(bundle_cli, "generate_bundle", lambda **kwargs: _bundle_result(kwargs["out_dir"]))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_demo_bundle.py",
            "--preset",
            "base",
            "--seed",
            "123",
            "--out",
            str(tmp_path / "bundle"),
        ],
    )

    assert bundle_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)

    assert "registry" not in payload


_GENERATED_FILES = [
    "manifest.json",
    "validation_report.json",
    "risk_flags.json",
    "scenario_review_memo.md",
]


def _fake_generate_bundle(
    *,
    preset: str,
    seed: int,
    out_dir: Path,
    n: int,
    sims_per_case: int,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-05-07T00:00:00Z"
    manifest = {
        "bundle_id": f"{preset}-{seed}",
        "generated_at_utc": generated_at,
        "generated_files": sorted(_GENERATED_FILES),
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
    risk_flags = {
        "contract_name": "risk_flags",
        "network_calls_made": False,
        "flags": [],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (out_dir / "validation_report.json").write_text(json.dumps(validation_report), encoding="utf-8")
    (out_dir / "risk_flags.json").write_text(json.dumps(risk_flags), encoding="utf-8")
    (out_dir / "scenario_review_memo.md").write_text("# Scenario Review Memo\n", encoding="utf-8")
    return _bundle_result(out_dir, manifest=manifest, validation_report=validation_report)


def _bundle_result(
    out_dir: Path,
    *,
    manifest: dict[str, Any] | None = None,
    validation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = "2026-05-07T00:00:00Z"
    manifest = manifest or {
        "bundle_id": "base-123",
        "generated_at_utc": generated_at,
        "generated_files": sorted(_GENERATED_FILES),
        "network_calls_made": False,
        "output_dir": str(out_dir),
        "preset": "base",
        "repo_commit": "abc1234",
        "seed": 123,
    }
    validation_report = validation_report or {
        "all_valid": True,
        "generated_at_utc": generated_at,
        "network_calls_made": False,
        "preset": "base",
        "seed": 123,
    }
    return {
        "bundle_dir": str(out_dir),
        "manifest": manifest,
        "validation_report": validation_report,
        "generated_files": sorted(_GENERATED_FILES),
    }


def _registry_rows(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {RUN_REGISTRY_TABLE}")]
