#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import logic_probe  # type: ignore


def test_invariants_pass():
    inv = logic_probe.invariants()
    # All invariant checks should be True
    assert all(bool(v) for v in inv.get("checks", {}).values())
