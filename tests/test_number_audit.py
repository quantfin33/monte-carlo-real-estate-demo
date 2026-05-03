from __future__ import annotations

import json

import pandas as pd

from button_audit import recompute_main_metrics, record_button_run
from scripts.number_audit import run_number_audit


def test_number_audit_writes_summary_and_report_for_passing_evidence(tmp_path) -> None:
    source = tmp_path / "button_audit"
    out = tmp_path / "number_audit"
    df = pd.DataFrame(
        {
            "IRR": [0.10, 0.15, 0.20],
            "NPV": [0.0, 1_000_000.0, 2_000_000.0],
            "CoC": [0.06, 0.08, 0.10],
            "EquityMultiple": [1.2, 1.4, 1.6],
            "Equity": [10_000_000.0, 10_000_000.0, 10_000_000.0],
        }
    )
    record_button_run("Run Monte Carlo Simulation", {"seed": 123}, df, {}, recompute_main_metrics(df), source)

    summary = run_number_audit(source, out)

    assert summary["overall_pass"] is True
    assert summary["status"] == "PASS"
    assert summary["button_run_count"] == 1
    assert summary["metric_tieout_count"] > 0
    assert (out / "summary.json").exists()
    assert (out / "analyst_report.md").exists()
    saved = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert saved["overall_pass"] is True


def test_number_audit_fails_on_p1_or_p2_mismatch(tmp_path) -> None:
    source = tmp_path / "button_audit"
    out = tmp_path / "number_audit"
    source.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "run_id": "run_1",
                "timestamp": "2026-05-03T09:00:00",
                "button_name": "Run Monte Carlo Simulation",
                "status": "FAIL",
                "row_count": 3,
                "metric_count": 1,
                "failed_count": 1,
                "p1_count": 1,
                "p2_count": 0,
                "input_json": "{}",
                "raw_csv": "raw.csv",
                "latest_raw_csv": "latest_raw.csv",
                "notes": "",
            }
        ]
    ).to_csv(source / "button_runs.csv", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "run_1",
                "timestamp": "2026-05-03T09:00:00",
                "button_name": "Run Monte Carlo Simulation",
                "metric": "IRR P50",
                "displayed_value": 15.0,
                "raw_value": 0.15,
                "recomputed_value": 14.0,
                "formula": "p50(IRR) * 100",
                "scale": "percent_points",
                "tolerance": 0.005,
                "delta": 1.0,
                "pass": False,
                "severity": "P1",
                "notes": "",
            }
        ]
    ).to_csv(source / "metric_tieouts.csv", index=False)

    summary = run_number_audit(source, out)

    assert summary["overall_pass"] is False
    assert summary["status"] == "FAIL"
    assert summary["p1_failures"] == 1
    assert "IRR P50" in (out / "analyst_report.md").read_text(encoding="utf-8")


def test_number_audit_no_data_is_nonblocking_but_classified(tmp_path) -> None:
    summary = run_number_audit(tmp_path / "missing", tmp_path / "number_audit")

    assert summary["overall_pass"] is True
    assert summary["status"] == "NO_DATA"
    assert summary["no_data"] is True
    assert summary["missing_files"]
