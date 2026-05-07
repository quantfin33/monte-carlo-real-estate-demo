from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.ui_control_audit import collect_controls


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "ui_control_classification.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _inventory_digest(controls: list[dict[str, object]]) -> str:
    canonical = json.dumps(controls, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _visibility_for_line(line: int, fixture: dict[str, Any]) -> str | None:
    for rule in fixture["visibility_ranges"]:
        if int(rule["start_line"]) <= line <= int(rule["end_line"]):
            return str(rule["name"])
    return None


def _classification_for_control(control: dict[str, object], fixture: dict[str, Any]) -> str | None:
    line = str(control["line"])
    label = str(control["label"])
    widget_type = str(control["type"])
    if line in fixture["classification_line_overrides"]:
        return str(fixture["classification_line_overrides"][line])
    if label in fixture["classification_label_overrides"]:
        return str(fixture["classification_label_overrides"][label])
    return fixture["default_classification_by_type"].get(widget_type)


def test_ui_control_inventory_matches_locked_surface() -> None:
    fixture = _load_fixture()
    controls = collect_controls()

    assert len(controls) == fixture["expected_total_controls"]
    assert _inventory_digest(controls) == fixture["expected_inventory_sha256"]
    assert dict(Counter(str(control["type"]) for control in controls)) == fixture[
        "expected_type_counts"
    ]


def test_every_ui_control_has_valid_classification_and_visibility() -> None:
    fixture = _load_fixture()
    controls = collect_controls()
    allowed = set(fixture["allowed_classifications"])

    unclassified: list[str] = []
    missing_visibility: list[str] = []
    invalid_classification: list[str] = []

    for control in controls:
        line = int(control["line"])
        label = str(control["label"])
        widget_type = str(control["type"])
        descriptor = f"line {line}: {widget_type} {label!r}"

        classification = _classification_for_control(control, fixture)
        if classification is None:
            unclassified.append(descriptor)
        elif classification not in allowed:
            invalid_classification.append(f"{descriptor} -> {classification!r}")

        if _visibility_for_line(line, fixture) is None:
            missing_visibility.append(descriptor)

    assert not unclassified, "Unclassified controls:\n" + "\n".join(unclassified)
    assert not invalid_classification, "Invalid classifications:\n" + "\n".join(
        invalid_classification
    )
    assert not missing_visibility, "Controls missing visibility group:\n" + "\n".join(
        missing_visibility
    )


def test_control_contract_fixture_has_no_dead_rules() -> None:
    fixture = _load_fixture()
    controls = collect_controls()
    labels = {str(control["label"]) for control in controls}
    lines = {str(control["line"]) for control in controls}

    dead_label_overrides = set(fixture["classification_label_overrides"]) - labels
    dead_line_overrides = set(fixture["classification_line_overrides"]) - lines

    assert not dead_label_overrides
    assert not dead_line_overrides
