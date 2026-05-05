#!/usr/bin/env python3
"""Dry-run or explicitly gated sandbox Odoo workflow sync.

Default behavior is offline dry-run planning. Sandbox writes require both Odoo
write env flags and the --allow-sandbox-write CLI flag.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from odoo_config import OdooConfigError, OdooConnectorConfig, OdooSafetyError
from odoo_handoff_payload import DEFAULT_OUTPUT_PATH, write_odoo_handoff_payload
from odoo_json2_client import OdooJson2Client
from odoo_model_discovery import build_fields_get_request
from odoo_sandbox_workflows import (
    ATTACHMENT_MODEL,
    CRM_LEAD_MODEL,
    PROJECT_TASK_MODEL,
    build_attachment_values,
    build_crm_lead_values,
    build_dry_run_sync_plan,
    build_message_post_request,
    build_project_task_values,
    build_sandbox_review_body,
    build_unlink_request,
    require_chatter_support,
    require_model_fields,
)


def main() -> int:
    args = _parse_args()
    payload_path = _ensure_payload_path(args.payload)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    if args.dry_run or not args.allow_sandbox_write:
        plan = build_dry_run_sync_plan(
            payload,
            artifact_path=payload_path,
            target_model=args.target_model or "project.task",
            target_record_id=args.target_record_id,
            project_id=args.project_id,
        )
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    return _run_sandbox_write(args, payload, payload_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or execute explicitly gated sandbox-only Odoo handoff workflows."
    )
    parser.add_argument("--dry-run", action="store_true", help="print offline plan only")
    parser.add_argument(
        "--allow-sandbox-write",
        action="store_true",
        help="execute sandbox writes when env guards also allow them",
    )
    parser.add_argument("--payload", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--target-model", default=None)
    parser.add_argument("--target-record-id", default=None)
    parser.add_argument("--project-id", default=None)
    return parser.parse_args()


def _ensure_payload_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.exists():
        write_odoo_handoff_payload(path)
    return path


def _run_sandbox_write(
    args: argparse.Namespace,
    payload: dict[str, Any],
    payload_path: Path,
) -> int:
    try:
        config = OdooConnectorConfig.from_env()
        config.require_database()
        client = OdooJson2Client(config)
    except (OdooConfigError, OdooSafetyError) as exc:
        print(f"Sandbox sync blocked: {exc}")
        return 1

    target_model = args.target_model or config.target_model
    target_record_id = args.target_record_id or config.target_record_id
    project_id = args.project_id or config.test_project_id
    missing = []
    if project_id is None:
        missing.append("ODOO_TEST_PROJECT_ID")
    if target_model is None:
        missing.append("ODOO_TARGET_MODEL")
    if target_record_id is None:
        missing.append("ODOO_TARGET_RECORD_ID")
    if missing:
        print(
            "Sandbox sync blocked: Missing required sandbox write configuration: "
            + ", ".join(missing)
        )
        return 1

    print("Sandbox sync config:")
    print(json.dumps(config.redacted_dict(), indent=2, sort_keys=True))
    created: list[dict[str, Any]] = []

    try:
        crm_fields = _fields_get(client, CRM_LEAD_MODEL)
        require_model_fields(crm_fields, ["name", "description"])
        crm_values = build_crm_lead_values(payload, crm_fields)
        crm_response = client.create(
            CRM_LEAD_MODEL,
            crm_values,
            target_metadata={"verified": True, "model": CRM_LEAD_MODEL},
        )
        crm_id = _extract_created_id(crm_response.result)
        created.append({"model": CRM_LEAD_MODEL, "id": crm_id, "purpose": "sandbox CRM lead"})

        task_fields = _fields_get(client, PROJECT_TASK_MODEL)
        require_model_fields(task_fields, ["name", "description", "project_id"])
        task_values = build_project_task_values(payload, project_id, task_fields)
        task_response = client.create(
            PROJECT_TASK_MODEL,
            task_values,
            target_metadata={"verified": True, "model": PROJECT_TASK_MODEL},
        )
        task_id = _extract_created_id(task_response.result)
        created.append(
            {"model": PROJECT_TASK_MODEL, "id": task_id, "purpose": "sandbox project task"}
        )

        attachment_fields = _fields_get(client, ATTACHMENT_MODEL)
        require_model_fields(attachment_fields, ["name", "type", "datas", "res_model", "res_id"])
        attachment_values = build_attachment_values(
            payload_path,
            target_model=target_model,
            target_record_id=target_record_id,
        )
        attachment_response = client.create(
            ATTACHMENT_MODEL,
            attachment_values,
            target_metadata={"verified": True, "model": ATTACHMENT_MODEL},
        )
        attachment_id = _extract_created_id(attachment_response.result)
        created.append(
            {"model": ATTACHMENT_MODEL, "id": attachment_id, "purpose": "sandbox JSON attachment"}
        )

        target_fields = _fields_get(client, target_model)
        require_chatter_support(target_fields)
        note_request = build_message_post_request(
            target_model,
            target_record_id,
            build_sandbox_review_body(payload),
        )
        note_response = client.call(
            note_request.model,
            note_request.method,
            params=note_request.params,
            ids=note_request.ids,
            context=note_request.context,
        )
        created.append(
            {
                "model": "mail.message",
                "id": _extract_created_id(note_response.result),
                "purpose": "sandbox chatter/internal note",
                "cleanup": "May require manual removal depending on target model permissions.",
            }
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "mode": "sandbox_write",
                    "status": "failed",
                    "error": str(exc),
                    "created_records": created,
                    "cleanup_requests": _cleanup_requests(created),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    output = {
        "mode": "sandbox_write",
        "created_records": created,
        "cleanup_requests": _cleanup_requests(created),
        "note": "Sandbox test records were created only because explicit write flags were enabled.",
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def _fields_get(client: OdooJson2Client, model: str) -> dict[str, Any]:
    request = build_fields_get_request(model)
    response = client.call(
        request.model,
        request.method,
        params=request.params,
        ids=request.ids,
        context=request.context,
    )
    if not isinstance(response.result, dict) or not response.result:
        raise OdooConfigError(f"fields_get for {model} did not return model metadata.")
    return response.result


def _extract_created_id(result: Any) -> int | None:
    if isinstance(result, bool):
        return None
    if isinstance(result, int):
        return result
    if isinstance(result, list) and result and isinstance(result[0], int):
        return result[0]
    if isinstance(result, dict) and isinstance(result.get("id"), int):
        return result["id"]
    return None


def _cleanup_requests(created: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleanup = []
    for item in created:
        if item["id"] is None or item["model"] == "mail.message":
            continue
        request = build_unlink_request(item["model"], item["id"])
        cleanup.append(
            {
                "model": item["model"],
                "path": request.path,
                "request": request.body(),
            }
        )
    return cleanup


if __name__ == "__main__":
    raise SystemExit(main())
