from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from run_registry import RUN_REGISTRY_TABLE, RunRegistryError, record_bundle_run
from scripts import generate_demo_bundle as bundle_cli
from scripts.generate_demo_bundle import generate_bundle


def test_registry_enabled_path_creates_single_audit_row(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    result = generate_bundle(
        preset="base",
        seed=123,
        out_dir=bundle_dir,
        n=3,
        sims_per_case=2,
        simulation_runner=_fake_runner,
        matrix_runner=_fake_runner,
    )

    db_path = tmp_path / "demo_runs.sqlite"
    registry = record_bundle_run(db_path, result)

    assert registry["enabled"] is True
    assert registry["db_path"] == str(db_path)
    rows = _registry_rows(db_path)
    assert len(rows) == 1

    row = rows[0]
    assert row["run_id"] == registry["run_id"]
    assert row["preset"] == "base"
    assert row["seed"] == 123
    assert row["generated_at_utc"] == result["manifest"]["generated_at_utc"]
    assert row["output_dir"] == str(bundle_dir)
    assert row["validation_status"] == "valid"
    assert row["validation_report_path"] == str(bundle_dir / "validation_report.json")
    assert json.loads(row["generated_files_json"]) == sorted(result["generated_files"])
    assert row["repo_commit"] == result["manifest"]["repo_commit"]
    assert row["network_calls_made"] == 0
    assert isinstance(row["created_at_utc"], str)


def test_registry_rejects_failed_validation_without_insert(tmp_path: Path) -> None:
    result = _bundle_result(tmp_path / "bundle")
    result["validation_report"] = {
        **result["validation_report"],
        "all_valid": False,
    }
    db_path = tmp_path / "demo_runs.sqlite"

    with pytest.raises(RunRegistryError, match="all_valid=true"):
        record_bundle_run(db_path, result)

    assert not db_path.exists()


def test_registry_rejects_network_calls_without_insert(tmp_path: Path) -> None:
    result = _bundle_result(tmp_path / "bundle")
    result["manifest"] = {
        **result["manifest"],
        "network_calls_made": True,
    }
    db_path = tmp_path / "demo_runs.sqlite"

    with pytest.raises(RunRegistryError, match="network_calls_made=false"):
        record_bundle_run(db_path, result)

    assert not db_path.exists()


def test_cli_without_registry_flag_keeps_output_shape(
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


def test_cli_registry_flag_adds_registry_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(bundle_cli, "generate_bundle", lambda **kwargs: _bundle_result(kwargs["out_dir"]))
    db_path = tmp_path / "demo_runs.sqlite"
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
            "--registry-db",
            str(db_path),
        ],
    )

    assert bundle_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["registry"]["enabled"] is True
    assert payload["registry"]["db_path"] == str(db_path)
    assert len(_registry_rows(db_path)) == 1


def _registry_rows(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {RUN_REGISTRY_TABLE}")]


def _bundle_result(out_dir: Path) -> dict[str, Any]:
    generated_at = "2026-05-06T00:00:00Z"
    generated_files = ["manifest.json", "validation_report.json"]
    return {
        "bundle_dir": str(out_dir),
        "manifest": {
            "bundle_id": "base-123",
            "generated_at_utc": generated_at,
            "generated_files": generated_files,
            "network_calls_made": False,
            "output_dir": str(out_dir),
            "preset": "base",
            "repo_commit": "abc1234",
            "seed": 123,
        },
        "validation_report": {
            "all_valid": True,
            "generated_at_utc": generated_at,
            "network_calls_made": False,
            "preset": "base",
            "seed": 123,
        },
        "generated_files": generated_files,
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
