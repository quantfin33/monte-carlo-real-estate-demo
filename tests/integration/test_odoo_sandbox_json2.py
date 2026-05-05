import os

import pytest

from odoo_config import OdooConnectorConfig
from odoo_json2_client import OdooJson2Client
from odoo_model_discovery import build_fields_get_request
from odoo_sandbox_workflows import (
    ATTACHMENT_MODEL,
    CRM_LEAD_MODEL,
    PROJECT_TASK_MODEL,
    build_attachment_values,
    build_crm_lead_values,
    build_message_post_request,
    build_project_task_values,
    build_sandbox_review_body,
    require_chatter_support,
    require_model_fields,
)


pytestmark = pytest.mark.integration


def _sandbox_env_ready() -> bool:
    if os.environ.get("ODOO_LIVE_ENABLED") != "true":
        return False
    return all(
        os.environ.get(name)
        for name in (
            "ODOO_BASE_URL",
            "ODOO_DATABASE",
            "ODOO_API_KEY",
            "ODOO_SANDBOX_CONFIRMATION",
            "ODOO_TARGET_MODEL",
        )
    )


def _sandbox_write_env_ready() -> bool:
    if not _sandbox_env_ready():
        return False
    return (
        os.environ.get("ODOO_ENABLE_LIVE_WRITES") == "true"
        and os.environ.get("PYTEST_ODOO_ALLOW_SANDBOX_WRITE") == "true"
    )


def _client() -> OdooJson2Client:
    config = OdooConnectorConfig.from_env()
    config.require_database()
    return OdooJson2Client(config)


def _fields_get(client: OdooJson2Client, model: str):
    request = build_fields_get_request(model)
    response = client.call(
        request.model,
        request.method,
        params=request.params,
        ids=request.ids,
        context=request.context,
    )
    assert response.ok is True
    assert isinstance(response.result, dict)
    assert response.result
    return response.result


def _handoff_payload():
    return {
        "source_simulation": {"scenario_name": "Sandbox validation scenario"},
        "metrics_summary": {},
        "explicit_non_claims": [
            "No production workflow automation is implemented.",
            "No investment advice is included.",
        ],
    }


@pytest.mark.skipif(
    not _sandbox_env_ready(),
    reason="Odoo sandbox env vars are not configured; skipping live read-only probe.",
)
def test_odoo_sandbox_read_only_fields_get_probe():
    result = _fields_get(_client(), os.environ["ODOO_TARGET_MODEL"])

    assert all(isinstance(metadata, dict) for metadata in result.values())


@pytest.mark.skipif(
    os.environ.get("ODOO_ENABLE_LIVE_WRITES") != "true"
    or os.environ.get("PYTEST_ODOO_ALLOW_SANDBOX_WRITE") != "true",
    reason="Sandbox write probe requires explicit env flags and is skipped by default.",
)
def test_odoo_sandbox_write_probe_is_not_enabled_in_this_phase():
    pytest.skip("Sandbox write execution is intentionally not implemented in this phase.")


@pytest.mark.skipif(
    not _sandbox_write_env_ready(),
    reason="Sandbox CRM lead write requires explicit env flags and is skipped by default.",
)
def test_odoo_sandbox_create_and_cleanup_crm_lead():
    client = _client()
    fields = _fields_get(client, CRM_LEAD_MODEL)
    require_model_fields(fields, ["name", "description"])
    values = build_crm_lead_values(_handoff_payload(), fields)

    response = client.create(
        CRM_LEAD_MODEL,
        values,
        target_metadata={"verified": True, "model": CRM_LEAD_MODEL},
    )
    record_id = response.result[0] if isinstance(response.result, list) else response.result
    try:
        assert isinstance(record_id, int)
    finally:
        if isinstance(record_id, int):
            client.unlink(
                CRM_LEAD_MODEL,
                [record_id],
                target_metadata={"verified": True, "model": CRM_LEAD_MODEL},
            )


@pytest.mark.skipif(
    not _sandbox_write_env_ready() or not os.environ.get("ODOO_TEST_PROJECT_ID"),
    reason="Sandbox project.task write requires explicit env flags and project id.",
)
def test_odoo_sandbox_create_and_cleanup_project_task():
    client = _client()
    fields = _fields_get(client, PROJECT_TASK_MODEL)
    require_model_fields(fields, ["name", "description", "project_id"])
    values = build_project_task_values(
        _handoff_payload(),
        os.environ["ODOO_TEST_PROJECT_ID"],
        fields,
    )

    response = client.create(
        PROJECT_TASK_MODEL,
        values,
        target_metadata={"verified": True, "model": PROJECT_TASK_MODEL},
    )
    record_id = response.result[0] if isinstance(response.result, list) else response.result
    try:
        assert isinstance(record_id, int)
    finally:
        if isinstance(record_id, int):
            client.unlink(
                PROJECT_TASK_MODEL,
                [record_id],
                target_metadata={"verified": True, "model": PROJECT_TASK_MODEL},
            )


@pytest.mark.skipif(
    not _sandbox_write_env_ready() or not os.environ.get("ODOO_TARGET_RECORD_ID"),
    reason="Sandbox attachment write requires explicit env flags and target record id.",
)
def test_odoo_sandbox_create_and_cleanup_attachment(tmp_path):
    client = _client()
    fields = _fields_get(client, ATTACHMENT_MODEL)
    require_model_fields(fields, ["name", "type", "datas", "res_model", "res_id"])
    artifact = tmp_path / "sandbox_payload.json"
    artifact.write_text('{"sandbox": true}', encoding="utf-8")
    values = build_attachment_values(
        artifact,
        target_model=os.environ["ODOO_TARGET_MODEL"],
        target_record_id=os.environ["ODOO_TARGET_RECORD_ID"],
    )

    response = client.create(
        ATTACHMENT_MODEL,
        values,
        target_metadata={"verified": True, "model": ATTACHMENT_MODEL},
    )
    record_id = response.result[0] if isinstance(response.result, list) else response.result
    try:
        assert isinstance(record_id, int)
    finally:
        if isinstance(record_id, int):
            client.unlink(
                ATTACHMENT_MODEL,
                [record_id],
                target_metadata={"verified": True, "model": ATTACHMENT_MODEL},
            )


@pytest.mark.skipif(
    not _sandbox_write_env_ready() or not os.environ.get("ODOO_TARGET_RECORD_ID"),
    reason="Sandbox chatter note requires explicit env flags and target record id.",
)
def test_odoo_sandbox_post_internal_note():
    client = _client()
    fields = _fields_get(client, os.environ["ODOO_TARGET_MODEL"])
    require_chatter_support(fields)
    request = build_message_post_request(
        os.environ["ODOO_TARGET_MODEL"],
        os.environ["ODOO_TARGET_RECORD_ID"],
        build_sandbox_review_body(_handoff_payload()),
    )

    response = client.call(
        request.model,
        request.method,
        params=request.params,
        ids=request.ids,
        context=request.context,
    )

    assert response.ok is True
