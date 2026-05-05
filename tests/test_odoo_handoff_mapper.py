from __future__ import annotations

import json
from pathlib import Path

from odoo_handoff_mapper import (
    ACTION_TYPES,
    build_odoo_dry_run_actions,
    redact_sensitive_values,
    write_odoo_dry_run_actions,
)
from odoo_handoff_payload import build_odoo_handoff_payload
from scripts.export_demo_business_summary import build_business_summary_payload


ROOT = Path(__file__).resolve().parents[1]


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return "\n".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value)


def _fixed_handoff_payload() -> dict[str, object]:
    business_summary = build_business_summary_payload(
        simulation_count=80,
        seed=12345,
        generated_at="2026-05-04T00:00:00Z",
    )
    return build_odoo_handoff_payload(
        business_summary,
        generated_at="2026-05-04T00:00:00Z",
        source_commit="testcommit",
    )


def test_dry_run_mapper_is_deterministic():
    payload = _fixed_handoff_payload()

    first = build_odoo_dry_run_actions(payload)
    second = build_odoo_dry_run_actions(payload)

    assert first == second
    assert first["schema_version"] == "odoo_handoff_dry_run.v1"
    assert first["execution_mode"] == "dry_run_only"


def test_dry_run_mapper_outputs_expected_action_types():
    action_plan = build_odoo_dry_run_actions(_fixed_handoff_payload())

    action_types = [action["action_type"] for action in action_plan["dry_run_actions"]]
    assert tuple(action_types) == ACTION_TYPES
    for action in action_plan["dry_run_actions"]:
        assert action["status"] == "not_executed"
        assert action["implemented_now"] is False
        assert action["would_call_api"] is False
        assert action["requires_target_database_model_verification"] is True


def test_dry_run_mapper_keeps_live_flags_false():
    action_plan = build_odoo_dry_run_actions(_fixed_handoff_payload())

    assert action_plan["local_demo_only"] is True
    assert action_plan["live_integration"] is False
    assert action_plan["live_writes_enabled"] is False
    assert action_plan["network_calls_made"] is False
    assert action_plan["connector_implemented"] is False
    assert action_plan["external_api_used"] is False
    assert action_plan["credentials_required"] is False
    assert action_plan["audit_trail"]["no_external_calls"] is True
    assert action_plan["audit_trail"]["no_environment_credentials_read"] is True
    assert action_plan["audit_trail"]["no_records_created"] is True


def test_dry_run_mapper_preserves_non_claims():
    action_plan = build_odoo_dry_run_actions(_fixed_handoff_payload())
    non_claims = "\n".join(action_plan["explicit_non_claims"]).lower()

    for phrase in [
        "no live odoo connector",
        "no erp sync",
        "no crm or sap integration",
        "live mcp server is not included",
        "no hosted api",
        "no production workflow automation",
        "no investment advice",
    ]:
        assert phrase in non_claims


def test_dry_run_mapper_contains_no_credentials_or_private_paths():
    action_plan = build_odoo_dry_run_actions(_fixed_handoff_payload())
    combined_text = _flatten_text(action_plan).lower()

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


def test_redaction_helper_masks_sensitive_values():
    value = {
        "ODOO_API_KEY": "abcdef123456",
        "nested": {
            "password": "supersecret",
            "safe": "visible",
        },
        "items": [
            {
                "access_token": "tok_123456789",
            }
        ],
    }

    redacted = redact_sensitive_values(value)

    assert redacted["ODOO_API_KEY"] == "<redacted:****3456>"
    assert redacted["nested"]["password"] == "<redacted:****cret>"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["access_token"] == "<redacted:****6789>"


def test_dry_run_mapper_handles_missing_optional_fields():
    action_plan = build_odoo_dry_run_actions({})

    assert action_plan["dry_run_actions"]
    assert "Input handoff payload was empty or invalid." in action_plan["warnings"]
    assert "Explicit non-claims were missing; default dry-run non-claims were applied." in action_plan["warnings"]
    assert action_plan["network_calls_made"] is False


def test_write_dry_run_actions_uses_supplied_output_path(tmp_path):
    output_path = tmp_path / "odoo_dry_run.json"

    write_odoo_dry_run_actions(output_path, _fixed_handoff_payload())

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "odoo_handoff_dry_run.v1"
    assert [action["action_type"] for action in payload["dry_run_actions"]] == list(ACTION_TYPES)


def test_mapper_does_not_import_network_or_odoo_modules():
    source = (ROOT / "odoo_handoff_mapper.py").read_text(encoding="utf-8").lower()

    forbidden_source_terms = [
        "import requests",
        "from requests",
        "import socket",
        "from socket",
        "xmlrpc",
        "jsonrpc",
        "/json/2",
        "import odoo",
        "from odoo",
        "urllib",
        "http.client",
    ]
    for term in forbidden_source_terms:
        assert term not in source
