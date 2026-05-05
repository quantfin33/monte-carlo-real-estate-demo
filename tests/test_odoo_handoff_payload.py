from __future__ import annotations

import json
import math
import re

from odoo_handoff_payload import build_odoo_handoff_payload, write_odoo_handoff_payload
from scripts.export_demo_business_summary import build_business_summary_payload


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return "\n".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value)


def _fixed_business_summary() -> dict[str, object]:
    return build_business_summary_payload(
        simulation_count=80,
        seed=12345,
        generated_at="2026-05-04T00:00:00Z",
    )


def test_odoo_handoff_payload_contract_is_deterministic():
    business_summary = _fixed_business_summary()

    first = build_odoo_handoff_payload(
        business_summary,
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )
    second = build_odoo_handoff_payload(
        business_summary,
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )

    assert first == second
    assert first["package_metadata"]["schema_version"] == "odoo_handoff_demo.v1"
    assert first["package_metadata"]["local_demo_only"] is True
    assert first["package_metadata"]["network_calls_made"] is False


def test_odoo_handoff_payload_has_required_sections_and_false_live_flags():
    payload = build_odoo_handoff_payload(
        _fixed_business_summary(),
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )

    required_top_level = {
        "generated_at",
        "package_metadata",
        "source_simulation",
        "proposed_odoo_target",
        "deal_summary",
        "metrics_summary",
        "risk_summary",
        "proposed_business_actions",
        "attachments",
        "audit_trail",
        "explicit_non_claims",
    }
    assert required_top_level.issubset(payload)

    target = payload["proposed_odoo_target"]
    assert target["target_system"] == "odoo_future"
    assert target["future_candidates_only"] is True
    assert target["requires_target_database_model_verification"] is True
    assert target["live_integration"] is False
    assert target["connector_implemented"] is False
    assert target["external_api_used"] is False


def test_odoo_handoff_payload_metrics_are_finite_where_available():
    payload = build_odoo_handoff_payload(
        _fixed_business_summary(),
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )

    for metric_name in [
        "irr",
        "npv",
        "cash_on_cash",
        "equity_multiple",
        "dscr",
        "debt_yield",
        "ltv",
        "exit_cap",
    ]:
        metric = payload["metrics_summary"][metric_name]
        assert metric["available"] is True
        assert isinstance(metric["p50"], float)
        assert math.isfinite(metric["p50"])


def test_odoo_handoff_payload_includes_risk_caveats_and_non_claims():
    payload = build_odoo_handoff_payload(
        _fixed_business_summary(),
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )

    assert payload["risk_summary"]["risk_flags"]
    assert payload["risk_summary"]["caveats"]

    combined_non_claims = "\n".join(payload["explicit_non_claims"]).lower()
    for phrase in [
        "no live odoo connector",
        "no erp sync",
        "no crm or sap integration",
        "live mcp server is not included",
        "no hosted api",
        "no production workflow automation",
        "no investment advice",
    ]:
        assert phrase in combined_non_claims


def test_odoo_handoff_payload_contains_no_secret_or_live_integration_markers():
    payload = build_odoo_handoff_payload(
        _fixed_business_summary(),
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )
    combined_text = _flatten_text(payload).lower()

    assert "openai_api_key" not in combined_text
    assert "api key" not in combined_text
    assert "password" not in combined_text
    assert "token" not in combined_text
    assert "credential" not in combined_text
    assert "sk-" not in combined_text
    assert "http://" not in combined_text
    assert "https://" not in combined_text
    assert "/users/chris" not in combined_text
    assert "desktop/backups" not in combined_text

    forbidden_positive_claims = [
        "odoo integration is implemented",
        "erp integration is implemented",
        "mcp server is implemented",
        "production-ready",
        "fully validated financial product",
    ]
    for phrase in forbidden_positive_claims:
        assert phrase not in combined_text

    assert not re.search(r"openai_api_key=.*sk-", combined_text)


def test_write_odoo_handoff_payload_uses_stable_artifact_shape(tmp_path):
    output_path = tmp_path / "sample_odoo_handoff_payload.json"

    write_odoo_handoff_payload(
        output_path=output_path,
        simulation_count=80,
        seed=12345,
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["attachments"][1]["relative_path"] == "artifacts/odoo_handoff_demo/sample_odoo_handoff_payload.json"
    assert payload["source_simulation"]["source_artifact"] == "artifacts/integration_demo/sample_business_summary.json"
