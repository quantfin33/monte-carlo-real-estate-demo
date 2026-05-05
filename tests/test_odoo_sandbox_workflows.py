import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

from odoo_handoff_payload import build_odoo_handoff_payload
from odoo_sandbox_workflows import (
    ATTACHMENT_MODEL,
    CRM_LEAD_MODEL,
    PROJECT_TASK_MODEL,
    CRM_LEAD_TEST_NAME,
    MAX_ATTACHMENT_BYTES,
    OdooWorkflowSafetyError,
    PROJECT_TASK_TEST_NAME,
    build_attachment_create_request,
    build_attachment_values,
    build_crm_lead_create_request,
    build_crm_lead_values,
    build_dry_run_sync_plan,
    build_message_post_request,
    build_project_task_create_request,
    build_project_task_values,
    build_unlink_request,
    require_chatter_support,
    require_model_fields,
)


def _handoff_payload():
    business_summary = {
        "package_metadata": {"seed": 12345, "simulation_count": 500},
        "scenario": {"name": "Base demo scenario"},
        "core_metrics": {
            "irr": {"p50": 0.12},
            "npv": {"p50": 1000000},
            "cash_on_cash": {"p50": 0.08},
            "equity_multiple": {"p50": 1.8},
        },
        "risk_flags": ["review assumptions"],
        "validation_boundary": {"scope": "demo"},
    }
    return build_odoo_handoff_payload(
        business_summary,
        generated_at="2026-05-05T00:00:00Z",
        source_commit="test",
    )


def test_crm_lead_create_request_shape():
    values = build_crm_lead_values(
        _handoff_payload(),
        {"name": {}, "description": {}, "type": {}},
    )
    request = build_crm_lead_create_request(values)

    assert request.path == "/json/2/crm.lead/create"
    assert request.body()["vals_list"][0]["name"] == CRM_LEAD_TEST_NAME
    assert request.body()["vals_list"][0]["type"] == "opportunity"
    assert "No investment advice" in request.body()["vals_list"][0]["description"]


def test_project_task_create_request_shape():
    values = build_project_task_values(
        _handoff_payload(),
        project_id=101,
        fields_metadata={"name": {}, "description": {}, "project_id": {}},
    )
    request = build_project_task_create_request(values)

    assert request.path == "/json/2/project.task/create"
    assert request.body()["vals_list"][0]["name"] == PROJECT_TASK_TEST_NAME
    assert request.body()["vals_list"][0]["project_id"] == 101


def test_project_task_requires_positive_project_id():
    with pytest.raises(OdooWorkflowSafetyError, match="positive integer"):
        build_project_task_values(_handoff_payload(), project_id=0)


def test_attachment_create_request_shape_and_payload_guard(tmp_path):
    artifact = tmp_path / "sample_payload.json"
    artifact.write_text(json.dumps({"safe": True}), encoding="utf-8")

    values = build_attachment_values(
        artifact,
        target_model="project.task",
        target_record_id=22,
    )
    request = build_attachment_create_request(values)

    assert request.path == "/json/2/ir.attachment/create"
    body = request.body()["vals_list"][0]
    assert body["name"] == "[SANDBOX TEST] sample_payload.json"
    assert body["res_model"] == "project.task"
    assert body["res_id"] == 22
    assert base64.b64decode(body["datas"]).decode("utf-8") == '{"safe": true}'


def test_attachment_rejects_unsupported_file_type(tmp_path):
    artifact = tmp_path / "payload.txt"
    artifact.write_text("safe", encoding="utf-8")

    with pytest.raises(OdooWorkflowSafetyError, match="Only local JSON"):
        build_attachment_values(artifact, target_model="project.task", target_record_id=1)


def test_attachment_rejects_secret_like_content(tmp_path):
    artifact = tmp_path / "payload.json"
    artifact.write_text('{"ODOO_API_KEY": "secret"}', encoding="utf-8")

    with pytest.raises(OdooWorkflowSafetyError, match="secret"):
        build_attachment_values(artifact, target_model="project.task", target_record_id=1)


def test_attachment_rejects_oversized_file(tmp_path):
    artifact = tmp_path / "payload.json"
    artifact.write_bytes(b"{" + (b" " * MAX_ATTACHMENT_BYTES) + b"}")

    with pytest.raises(OdooWorkflowSafetyError, match="size guard"):
        build_attachment_values(artifact, target_model="project.task", target_record_id=1)


def test_message_post_request_shape():
    request = build_message_post_request(
        "project.task",
        22,
        "Sandbox validation note. No production workflow automation or investment advice.",
    )

    assert request.path == "/json/2/project.task/message_post"
    assert request.body()["ids"] == [22]
    assert request.body()["subtype_xmlid"] == "mail.mt_note"


def test_chatter_support_guard():
    require_chatter_support({"message_ids": {}, "name": {}})
    with pytest.raises(OdooWorkflowSafetyError, match="chatter"):
        require_chatter_support({"name": {}})


def test_required_field_validation_guard():
    require_model_fields({"name": {}, "description": {}}, ["name"])
    with pytest.raises(OdooWorkflowSafetyError, match="missing required fields"):
        require_model_fields({"name": {}}, ["name", "description"])


def test_unlink_cleanup_request_shape():
    request = build_unlink_request(CRM_LEAD_MODEL, 55)

    assert request.path == "/json/2/crm.lead/unlink"
    assert request.body()["ids"] == [55]


def test_dry_run_sync_plan_preserves_offline_flags(tmp_path):
    artifact = tmp_path / "payload.json"
    artifact.write_text(json.dumps({"safe": True}), encoding="utf-8")

    plan = build_dry_run_sync_plan(
        _handoff_payload(),
        artifact_path=artifact,
        target_model=PROJECT_TASK_MODEL,
        target_record_id=22,
        project_id=101,
    )

    assert plan["network_calls_made"] is False
    assert plan["live_integration"] is False
    assert plan["external_api_used"] is False
    assert {action["action"] for action in plan["actions"]} == {
        "would_create_crm_lead",
        "would_create_project_task",
        "would_attach_json_artifact",
        "would_post_internal_note",
    }
    assert ATTACHMENT_MODEL in plan["actions"][2]["path"]


def test_sandbox_sync_cli_dry_run_preserves_offline_flags():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/odoo_sandbox_sync.py", "--dry-run"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["network_calls_made"] is False
    assert payload["live_integration"] is False
    assert payload["external_api_used"] is False
    assert payload["mode"] == "dry_run"
