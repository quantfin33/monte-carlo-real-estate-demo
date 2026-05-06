#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOGIC_REPORT = ROOT / "artifacts" / "logic_report.json"


def test_included_logic_report_invariants_pass() -> None:
    report = json.loads(LOGIC_REPORT.read_text(encoding="utf-8"))

    assert report["all_pass"] is True
    assert all(item["pass"] is True for item in report["directions"].values())
    assert all(item["pass"] is True for item in report["occupancy"].values())
    assert all(item["present"] is True for item in report["percentiles"].values())
    assert all(item["monotonic"] is True for item in report["percentiles"].values())
    assert report["trace_irr"]["pass"] is True
