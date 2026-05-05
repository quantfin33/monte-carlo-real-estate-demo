from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def run_number_audit(source_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    button_runs_path = source_path / "button_runs.csv"
    metric_tieouts_path = source_path / "metric_tieouts.csv"
    missing_files = [
        str(path)
        for path in [button_runs_path, metric_tieouts_path]
        if not path.exists()
    ]

    if missing_files:
        summary = {
            "overall_pass": True,
            "status": "NO_DATA",
            "no_data": True,
            "missing_files": missing_files,
            "button_run_count": 0,
            "metric_tieout_count": 0,
            "p1_failures": 0,
            "p2_failures": 0,
        }
        _write_outputs(summary, pd.DataFrame(), output_path)
        return summary

    button_runs = pd.read_csv(button_runs_path)
    tieouts = pd.read_csv(metric_tieouts_path)
    pass_col = tieouts.get("pass", pd.Series(dtype=bool)).astype(str).str.lower()
    failing = tieouts[pass_col != "true"]
    p1_failures = int((failing.get("severity", pd.Series(dtype=str)) == "P1").sum()) if not failing.empty else 0
    p2_failures = int((failing.get("severity", pd.Series(dtype=str)) == "P2").sum()) if not failing.empty else 0
    overall_pass = p1_failures == 0 and p2_failures == 0

    summary = {
        "overall_pass": overall_pass,
        "status": "PASS" if overall_pass else "FAIL",
        "no_data": False,
        "missing_files": [],
        "button_run_count": int(len(button_runs)),
        "metric_tieout_count": int(len(tieouts)),
        "p1_failures": p1_failures,
        "p2_failures": p2_failures,
    }
    _write_outputs(summary, failing, output_path)
    return summary


def _write_outputs(summary: dict[str, Any], failing: pd.DataFrame, output_path: Path) -> None:
    (output_path / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Number Audit Report",
        "",
        f"Status: {summary['status']}",
        f"Button runs: {summary['button_run_count']}",
        f"Metric tie-outs: {summary['metric_tieout_count']}",
    ]
    if summary.get("missing_files"):
        lines.extend(["", "Missing evidence files:"])
        lines.extend(f"- {item}" for item in summary["missing_files"])
    if not failing.empty:
        lines.extend(["", "Failing tie-outs:"])
        for _, row in failing.iterrows():
            lines.append(f"- {row.get('metric', 'unknown metric')} ({row.get('severity', 'unclassified')})")

    (output_path / "analyst_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
