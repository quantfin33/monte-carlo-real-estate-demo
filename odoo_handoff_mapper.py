from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "odoo_handoff_dry_run.v1"

DRY_RUN_NON_CLAIMS = [
    "No live Odoo connector is implemented.",
    "No ERP sync is implemented.",
    "No CRM or SAP integration is implemented.",
    "A live MCP server is not included.",
    "No hosted API is implemented.",
    "No production workflow automation is implemented.",
    "No investment advice is included.",
]

ACTION_TYPES = (
    "would_create_review_task",
    "would_attach_report",
    "would_add_internal_note",
    "would_request_assumption_review",
)

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "token",
)


def build_odoo_dry_run_actions(handoff_payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a local handoff payload into future Odoo action candidates.

    This mapper is intentionally offline. It does not read environment variables,
    import network clients, or attempt to discover Odoo models.
    """

    payload = handoff_payload if isinstance(handoff_payload, dict) else {}
    metadata = _dict(payload.get("package_metadata"))
    source = _dict(payload.get("source_simulation"))
    target = _dict(payload.get("proposed_odoo_target"))
    metrics = _dict(payload.get("metrics_summary"))
    risk_summary = _dict(payload.get("risk_summary"))
    audit_trail = _dict(payload.get("audit_trail"))
    attachments = _list(payload.get("attachments"))
    non_claims = _list(payload.get("explicit_non_claims")) or list(DRY_RUN_NON_CLAIMS)

    scenario_name = _text(source.get("scenario_name"), "Current simulation")
    risk_flags = [str(flag) for flag in _list(risk_summary.get("risk_flags"))]
    caveats = [str(caveat) for caveat in _list(risk_summary.get("caveats"))]

    action_plan = {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": "dry_run_only",
        "local_demo_only": True,
        "live_integration": False,
        "live_writes_enabled": False,
        "network_calls_made": False,
        "connector_implemented": False,
        "external_api_used": False,
        "credentials_required": False,
        "source_handoff": {
            "schema_version": metadata.get("schema_version"),
            "artifact_type": metadata.get("artifact_type"),
            "source_commit": metadata.get("source_commit"),
            "generated_at": metadata.get("generated_at") or payload.get("generated_at"),
        },
        "target_boundary": {
            "target_system": target.get("target_system", "odoo_future"),
            "future_candidates_only": True,
            "requires_target_database_model_verification": True,
            "suggested_record_types": _list(target.get("suggested_record_types")),
            "suggested_model_names_future_candidates": _list(
                target.get("suggested_model_names_future_candidates")
            ),
        },
        "dry_run_actions": [
            _review_task_action(scenario_name, metrics, risk_flags, caveats, non_claims),
            _attach_report_action(attachments),
            _internal_note_action(scenario_name, metrics, risk_flags, non_claims),
            _assumption_review_action(scenario_name, risk_flags, caveats),
        ],
        "audit_trail": {
            "source_business_summary_generated_at": audit_trail.get("source_business_summary_generated_at"),
            "source_handoff_generated_at": payload.get("generated_at"),
            "assumptions_preserved": bool(audit_trail.get("assumptions_preserved", True)),
            "no_external_calls": True,
            "no_environment_credentials_read": True,
            "no_records_created": True,
        },
        "warnings": _warnings_for_payload(payload),
        "explicit_non_claims": [str(claim) for claim in non_claims],
    }
    return redact_sensitive_values(action_plan)


def write_odoo_dry_run_actions(
    output_path: Path | str,
    handoff_payload: dict[str, Any],
) -> Path:
    action_plan = build_odoo_dry_run_actions(handoff_payload)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(action_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def redact_sensitive_values(value: Any) -> Any:
    """Recursively redact values whose keys look sensitive."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = _redact_scalar(item)
            else:
                redacted[key_text] = redact_sensitive_values(item)
        return redacted

    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]

    return value


def _review_task_action(
    scenario_name: str,
    metrics: dict[str, Any],
    risk_flags: list[str],
    caveats: list[str],
    non_claims: list[Any],
) -> dict[str, Any]:
    return _action(
        action_type="would_create_review_task",
        future_odoo_concept="project task or CRM activity",
        future_model_candidates=["project.task", "crm.lead"],
        values={
            "title": f"Review Monte Carlo scenario: {scenario_name}",
            "description": _metrics_brief(metrics),
            "review_checklist": risk_flags or ["Review current simulation assumptions."],
            "caveats": caveats,
            "non_claim_footer": [str(claim) for claim in non_claims],
        },
    )


def _attach_report_action(attachments: list[Any]) -> dict[str, Any]:
    safe_attachments = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        safe_attachments.append(
            {
                "filename": attachment.get("filename"),
                "relative_path": attachment.get("relative_path"),
                "purpose": attachment.get("purpose"),
                "generated_in_current_package": bool(attachment.get("generated_in_current_package")),
            }
        )

    return _action(
        action_type="would_attach_report",
        future_odoo_concept="document attachment",
        future_model_candidates=["ir.attachment"],
        values={
            "attachments": safe_attachments,
            "attachment_note": "Future attachment only; no file was sent to Odoo.",
        },
    )


def _internal_note_action(
    scenario_name: str,
    metrics: dict[str, Any],
    risk_flags: list[str],
    non_claims: list[Any],
) -> dict[str, Any]:
    return _action(
        action_type="would_add_internal_note",
        future_odoo_concept="record note or chatter message",
        future_model_candidates=["mail.message"],
        values={
            "subject": f"Monte Carlo handoff summary: {scenario_name}",
            "body": "\n".join(
                [
                    _metrics_brief(metrics),
                    "Risk flags: " + ("; ".join(risk_flags) if risk_flags else "none supplied"),
                    "Boundary: " + "; ".join(str(claim) for claim in non_claims),
                ]
            ),
        },
    )


def _assumption_review_action(
    scenario_name: str,
    risk_flags: list[str],
    caveats: list[str],
) -> dict[str, Any]:
    return _action(
        action_type="would_request_assumption_review",
        future_odoo_concept="approval or review activity",
        future_model_candidates=["project.task", "crm.lead"],
        values={
            "title": f"Assumption review required: {scenario_name}",
            "risk_items": risk_flags,
            "review_caveats": caveats,
            "routing_note": "Human review required before any business reliance.",
        },
    )


def _action(
    *,
    action_type: str,
    future_odoo_concept: str,
    future_model_candidates: list[str],
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action_type": action_type,
        "status": "not_executed",
        "implemented_now": False,
        "would_call_api": False,
        "future_odoo_concept": future_odoo_concept,
        "future_model_candidates": future_model_candidates,
        "requires_target_database_model_verification": True,
        "values": values,
    }


def _metrics_brief(metrics: dict[str, Any]) -> str:
    labels = [
        ("irr", "IRR"),
        ("npv", "NPV"),
        ("cash_on_cash", "Cash-on-Cash"),
        ("equity_multiple", "Equity Multiple"),
        ("dscr", "DSCR"),
        ("debt_yield", "Debt Yield"),
        ("ltv", "LTV"),
        ("exit_cap", "Exit Cap"),
    ]
    parts: list[str] = []
    for key, label in labels:
        metric = _dict(metrics.get(key))
        if not metric.get("available") or "p50" not in metric:
            continue
        parts.append(f"{label} P50={metric['p50']}")
    return "Metrics: " + (", ".join(parts) if parts else "not available in current handoff payload")


def _warnings_for_payload(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not payload:
        warnings.append("Input handoff payload was empty or invalid.")
    if not _dict(payload.get("metrics_summary")):
        warnings.append("Metrics summary is missing; dry-run note will be limited.")
    if not _list(payload.get("explicit_non_claims")):
        warnings.append("Explicit non-claims were missing; default dry-run non-claims were applied.")
    warnings.append("Dry run only; no Odoo record, attachment, note, task, or approval activity was created.")
    return warnings


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if value is None:
        return "<redacted>"
    text = str(value)
    if len(text) <= 4:
        return "<redacted>"
    return f"<redacted:****{text[-4:]}>"


def _dict(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return copy.deepcopy(value) if isinstance(value, list) else []


def _text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
