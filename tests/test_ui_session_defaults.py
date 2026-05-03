#!/usr/bin/env python3
"""Minimal guard for UI session defaults.

Ensures renewal concession keys are initialized to avoid AttributeError when
the form reads them before first submit.
This is a static check on the source text (no Streamlit runtime needed).
"""
from pathlib import Path

def test_renewal_defaults_present():
    ui = Path(__file__).resolve().parents[1] / "UI.py"
    txt = ui.read_text(encoding="utf-8", errors="ignore")
    assert '"renew_free_months": None' in txt
    assert '"renew_downtime_months": None' in txt

