"""Sandbox-only Odoo workflow request builders.

This module does not make network calls. It converts the local handoff payload
into explicitly marked sandbox test operations for a separately gated client.
"""

from __future__ import annotations

import base64
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from odoo_connector_contract import OdooJson2Request
from odoo_model_discovery import validate_required_fields


CRM_LEAD_MODEL = "crm.lead"
PROJECT_TASK_MODEL = "project.task"
ATTACHMENT_MODEL = "ir.attachment"

CRM_LEAD_TEST_NAME = "[SANDBOX TEST] Monte Carlo handoff validation"
PROJECT_TASK_TEST_NAME = "[SANDBOX TEST] Review Monte Carlo scenario"
SANDBOX_NOTE_BODY = (
    "Sandbox validation note. No production workflow automation or investment advice."
)
MAX_ATTACHMENT_BYTES = 1_000_000
SUPPORTED_ATTACHMENT_SUFFIXES = {".json"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY[\"']?\s*[:=]", re.IGNORECASE),
    re.compile(r"ODOO_API_KEY[\"']?\s*[:=]", re.IGNORECASE),
    re.compile(r"Authorization[\"']?\s*:\s*bearer\s+\S+", re.IGNORECASE),
)


class OdooWorkflowSafetyError(ValueError):
    """Raised when a sandbox workflow payload is unsafe or not validated."""


def build_crm_lead_values(
    handoff_payload: Mapping[str, Any],
    fields_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values = {
        "name": CRM_LEAD_TEST_NAME,
        "description": build_sandbox_review_body(handoff_payload),
    }
    if fields_metadata is None or "type" in fields_metadata:
        values["type"] = "opportunity"
    return _filter_to_fields(values, fields_metadata)


def build_project_task_values(
    handoff_payload: Mapping[str, Any],
    project_id: int | str,
    fields_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    parsed_project_id = _positive_int(project_id, "ODOO_TEST_PROJECT_ID")
    values = {
        "name": PROJECT_TASK_TEST_NAME,
        "description": build_sandbox_review_body(handoff_payload),
        "project_id": parsed_project_id,
    }
    return _filter_to_fields(values, fields_metadata)


def build_attachment_values(
    artifact_path: Path | str,
    *,
    target_model: str,
    target_record_id: int | str,
    description: str = "Sandbox/test-only Monte Carlo handoff JSON artifact.",
) -> dict[str, Any]:
    path = Path(artifact_path)
    _validate_attachment_file(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    _assert_no_secret_text(text)
    json.loads(text)
    return {
        "name": f"[SANDBOX TEST] {path.name}",
        "type": "binary",
        "datas": base64.b64encode(raw).decode("ascii"),
        "res_model": target_model,
        "res_id": _positive_int(target_record_id, "target_record_id"),
        "mimetype": "application/json",
        "description": description,
    }


def build_sandbox_review_body(handoff_payload: Mapping[str, Any]) -> str:
    metrics = handoff_payload.get("metrics_summary", {})
    non_claims = handoff_payload.get("explicit_non_claims", [])
    lines = [
        SANDBOX_NOTE_BODY,
        "",
        "Source: local Monte Carlo Odoo handoff payload.",
        f"Scenario: {_source_scenario_name(handoff_payload)}",
        "",
        "Selected metrics:",
    ]
    for label in ("irr", "npv", "cash_on_cash", "equity_multiple"):
        lines.append(f"- {label}: {_metric_p50(metrics, label)}")
    lines.extend(["", "Boundary / non-claims:"])
    for claim in non_claims:
        lines.append(f"- {claim}")
    return "\n".join(lines)


def build_crm_lead_create_request(values: Mapping[str, Any]) -> OdooJson2Request:
    return build_create_request(CRM_LEAD_MODEL, values)


def build_project_task_create_request(values: Mapping[str, Any]) -> OdooJson2Request:
    return build_create_request(PROJECT_TASK_MODEL, values)


def build_attachment_create_request(values: Mapping[str, Any]) -> OdooJson2Request:
    return build_create_request(ATTACHMENT_MODEL, values)


def build_create_request(model: str, values: Mapping[str, Any]) -> OdooJson2Request:
    return OdooJson2Request(model=model, method="create", params={"vals_list": [dict(values)]})


def build_message_post_request(
    target_model: str,
    target_record_id: int | str,
    body: str,
) -> OdooJson2Request:
    return OdooJson2Request(
        model=target_model,
        method="message_post",
        ids=[_positive_int(target_record_id, "target_record_id")],
        params={
            "body": body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
        },
    )


def build_unlink_request(model: str, record_id: int | str) -> OdooJson2Request:
    return OdooJson2Request(
        model=model,
        method="unlink",
        ids=[_positive_int(record_id, "record_id")],
    )


def require_model_fields(
    fields_metadata: Mapping[str, Any],
    required_fields: list[str],
) -> dict[str, Any]:
    result = validate_required_fields(fields_metadata, required_fields)
    if not result["verified"]:
        raise OdooWorkflowSafetyError(
            "Target model is missing required fields: "
            + ", ".join(result["missing_fields"])
        )
    return result


def model_supports_chatter(fields_metadata: Mapping[str, Any]) -> bool:
    return any(
        field in fields_metadata
        for field in ("message_ids", "message_follower_ids", "activity_ids")
    )


def require_chatter_support(fields_metadata: Mapping[str, Any]) -> None:
    if not model_supports_chatter(fields_metadata):
        raise OdooWorkflowSafetyError(
            "Target model metadata does not show chatter/mail-thread fields."
        )


def build_dry_run_sync_plan(
    handoff_payload: Mapping[str, Any],
    *,
    artifact_path: Path | str,
    target_model: str = PROJECT_TASK_MODEL,
    target_record_id: int | str | None = None,
    project_id: int | str | None = None,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    crm_values = build_crm_lead_values(handoff_payload)
    actions.append(_request_preview("would_create_crm_lead", build_crm_lead_create_request(crm_values)))

    if project_id is not None:
        task_values = build_project_task_values(handoff_payload, project_id)
        actions.append(
            _request_preview("would_create_project_task", build_project_task_create_request(task_values))
        )
    else:
        actions.append(
            {
                "action": "would_create_project_task",
                "status": "blocked",
                "reason": "ODOO_TEST_PROJECT_ID is required for project.task association.",
            }
        )

    if target_record_id is not None:
        attachment_values = build_attachment_values(
            artifact_path,
            target_model=target_model,
            target_record_id=target_record_id,
        )
        safe_attachment_values = dict(attachment_values)
        safe_attachment_values["datas"] = "<base64 JSON omitted from dry-run summary>"
        actions.append(
            _request_preview(
                "would_attach_json_artifact",
                build_attachment_create_request(safe_attachment_values),
            )
        )
        note_request = build_message_post_request(
            target_model,
            target_record_id,
            build_sandbox_review_body(handoff_payload),
        )
        actions.append(_request_preview("would_post_internal_note", note_request))
    else:
        actions.append(
            {
                "action": "would_attach_json_artifact",
                "status": "blocked",
                "reason": "ODOO_TARGET_RECORD_ID is required for attachment upload.",
            }
        )
        actions.append(
            {
                "action": "would_post_internal_note",
                "status": "blocked",
                "reason": "ODOO_TARGET_RECORD_ID is required for chatter note posting.",
            }
        )

    return {
        "mode": "dry_run",
        "network_calls_made": False,
        "live_integration": False,
        "external_api_used": False,
        "default_execution": "offline preview only",
        "actions": actions,
        "cleanup_strategy": [
            "Sandbox writes, if explicitly enabled later, must record created IDs.",
            "Use build_unlink_request(model, record_id) or Odoo unlink to remove test CRM/task/attachment records.",
            "Chatter notes may require manual removal depending on target model permissions.",
        ],
    }


def _request_preview(action: str, request: OdooJson2Request) -> dict[str, Any]:
    return {
        "action": action,
        "status": "planned_dry_run_only",
        "method": "POST",
        "path": request.path,
        "json_body": request.body(),
        "created_record": False,
    }


def _filter_to_fields(
    values: dict[str, Any],
    fields_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if fields_metadata is None:
        return values
    return {key: value for key, value in values.items() if key in fields_metadata}


def _validate_attachment_file(path: Path) -> None:
    if not path.exists():
        raise OdooWorkflowSafetyError(f"Attachment file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_ATTACHMENT_SUFFIXES:
        raise OdooWorkflowSafetyError("Only local JSON artifacts are supported for sandbox upload.")
    if path.stat().st_size > MAX_ATTACHMENT_BYTES:
        raise OdooWorkflowSafetyError("Attachment exceeds the sandbox size guard.")


def _assert_no_secret_text(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise OdooWorkflowSafetyError("Attachment text appears to contain a secret.")


def _positive_int(value: int | str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OdooWorkflowSafetyError(f"{label} must be a positive integer.") from exc
    if parsed <= 0:
        raise OdooWorkflowSafetyError(f"{label} must be a positive integer.")
    return parsed


def _source_scenario_name(handoff_payload: Mapping[str, Any]) -> str:
    source = handoff_payload.get("source_simulation", {})
    if isinstance(source, Mapping):
        return str(source.get("scenario_name", "Base demo scenario"))
    return "Base demo scenario"


def _metric_p50(metrics_summary: Any, key: str) -> str:
    if not isinstance(metrics_summary, Mapping):
        return "not available"
    metric = metrics_summary.get(key)
    if not isinstance(metric, Mapping):
        return "not available"
    value = metric.get("p50")
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return str(value)
    return "not available"
