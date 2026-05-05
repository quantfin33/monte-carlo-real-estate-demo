from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.export_demo_business_summary import build_business_summary_payload

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "odoo_handoff_demo" / "sample_odoo_handoff_payload.json"
SOURCE_BUSINESS_SUMMARY_ARTIFACT = "artifacts/integration_demo/sample_business_summary.json"

SCHEMA_VERSION = "odoo_handoff_demo.v1"

EXPLICIT_NON_CLAIMS = [
    "No live Odoo connector is implemented.",
    "No ERP sync is implemented.",
    "No CRM or SAP integration is implemented.",
    "A live MCP server is not included.",
    "No hosted API is implemented.",
    "No production workflow automation is implemented.",
    "No investment advice is included.",
]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _metric_summary(core_metrics: dict[str, Any], key: str, label: str, unit: str) -> dict[str, Any]:
    source = core_metrics.get(key) if isinstance(core_metrics, dict) else {}
    if not isinstance(source, dict):
        source = {}

    entry: dict[str, Any] = {
        "label": label,
        "unit": unit,
        "available": False,
    }
    for percentile_key in ("p5", "p50", "p95"):
        value = _finite_or_none(source.get(percentile_key))
        if value is not None:
            entry[percentile_key] = value
            entry["available"] = True
    return entry


def _unavailable_field(label: str, reason: str) -> dict[str, str]:
    return {
        "field": label,
        "reason": reason,
    }


def build_odoo_handoff_payload(
    business_summary: dict[str, Any],
    generated_at: str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Build a local-only future Odoo/ERP handoff payload from the business summary export."""

    generated = generated_at or _utc_timestamp()
    metadata = business_summary.get("package_metadata") if isinstance(business_summary, dict) else {}
    scenario = business_summary.get("scenario") if isinstance(business_summary, dict) else {}
    core_metrics = business_summary.get("core_metrics") if isinstance(business_summary, dict) else {}
    validation_boundary = business_summary.get("validation_boundary") if isinstance(business_summary, dict) else {}
    risk_flags = business_summary.get("risk_flags") if isinstance(business_summary, dict) else []

    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(scenario, dict):
        scenario = {}
    if not isinstance(core_metrics, dict):
        core_metrics = {}
    if not isinstance(validation_boundary, dict):
        validation_boundary = {}
    if not isinstance(risk_flags, list):
        risk_flags = []

    unavailable_deal_fields = [
        _unavailable_field("Purchase price", "Not included in the current business-summary export."),
        _unavailable_field("Total RSF", "Not included in the current business-summary export."),
        _unavailable_field("Initial occupancy", "Not included in the current business-summary export."),
        _unavailable_field("Detailed lease records", "Future Odoo/ERP mapping candidate only."),
    ]

    return {
        "generated_at": generated,
        "package_metadata": {
            "name": "monte-carlo-real-estate-demo",
            "artifact_type": "local Odoo/ERP handoff payload demo",
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated,
            "source_app": "Streamlit Monte Carlo real-estate analytics dashboard",
            "source_commit": source_commit if source_commit is not None else _git_commit(),
            "local_demo_only": True,
            "network_calls_made": False,
        },
        "source_simulation": {
            "scenario_name": scenario.get("name", "Base demo scenario"),
            "scenario_description": scenario.get("description"),
            "seed": metadata.get("seed"),
            "simulation_count": metadata.get("simulation_count"),
            "source_artifact": SOURCE_BUSINESS_SUMMARY_ARTIFACT,
            "source_export_type": metadata.get("artifact_type", "local deterministic business-summary export"),
            "generated_from": "scripts.export_demo_business_summary.build_business_summary_payload",
            "model_source": metadata.get("source", "monte_carlo_model.run_simulation"),
        },
        "proposed_odoo_target": {
            "target_system": "odoo_future",
            "suggested_record_types": [
                "opportunity",
                "project",
                "document",
                "review task",
            ],
            "suggested_model_names_future_candidates": [
                "crm.lead",
                "project.task",
                "ir.attachment",
                "mail.message",
            ],
            "future_candidates_only": True,
            "requires_target_database_model_verification": True,
            "live_integration": False,
            "connector_implemented": False,
            "external_api_used": False,
        },
        "deal_summary": {
            "deal_title": scenario.get("name", "Base demo scenario"),
            "description": scenario.get("description"),
            "available_fields": {
                "scenario_name": scenario.get("name", "Base demo scenario"),
                "scenario_description": scenario.get("description"),
            },
            "unavailable_fields": unavailable_deal_fields,
            "key_assumption_note": "Detailed property and lease assumptions remain in the dashboard/model layer; this local payload maps only the current reviewed summary export.",
        },
        "metrics_summary": {
            "irr": _metric_summary(core_metrics, "irr", "IRR", "decimal_rate"),
            "npv": _metric_summary(core_metrics, "npv", "NPV", "dollars"),
            "cash_on_cash": _metric_summary(core_metrics, "cash_on_cash", "Cash-on-Cash", "decimal_rate"),
            "equity_multiple": _metric_summary(core_metrics, "equity_multiple", "Equity Multiple", "multiple"),
            "dscr": _metric_summary(core_metrics, "dscr", "DSCR", "ratio"),
            "debt_yield": _metric_summary(core_metrics, "debt_yield", "Debt Yield", "decimal_rate"),
            "ltv": _metric_summary(core_metrics, "ltv", "LTV", "decimal_rate"),
            "exit_cap": _metric_summary(core_metrics, "exit_cap", "Exit Cap", "decimal_rate"),
        },
        "risk_summary": {
            "risk_flags": [str(flag) for flag in risk_flags],
            "review_warnings": [
                "Strong or weak metrics should be reviewed against assumptions before business reliance.",
                "Future workflow records should route the analysis for human review rather than automated approval.",
            ],
            "missing_or_unsupported_fields": unavailable_deal_fields,
            "caveats": [
                "This payload is a local handoff demonstration only.",
                "No Odoo, ERP, CRM, SAP, MCP, or hosted API record was created.",
                "Sensitivity and financial interpretation remain inside the demo/local-review boundary.",
            ],
        },
        "proposed_business_actions": [
            {
                "action": "create_review_task",
                "future_odoo_concept": "project task or CRM activity",
                "description": "Ask a reviewer to inspect assumptions, risk flags, and exported metrics.",
                "implemented_now": False,
            },
            {
                "action": "attach_report_bundle",
                "future_odoo_concept": "document attachment",
                "description": "Attach reviewed JSON/CSV/report artifacts to a future deal or project record.",
                "implemented_now": False,
            },
            {
                "action": "add_internal_note",
                "future_odoo_concept": "record note or chatter message",
                "description": "Summarize model outputs and caveats for internal review.",
                "implemented_now": False,
            },
            {
                "action": "request_assumption_review",
                "future_odoo_concept": "approval or review activity",
                "description": "Route key assumptions and flagged metrics for human approval review.",
                "implemented_now": False,
            },
        ],
        "attachments": [
            {
                "filename": "sample_business_summary.json",
                "relative_path": SOURCE_BUSINESS_SUMMARY_ARTIFACT,
                "purpose": "Source model summary for future business-system handoff.",
                "generated_in_current_package": True,
            },
            {
                "filename": "sample_odoo_handoff_payload.json",
                "relative_path": "artifacts/odoo_handoff_demo/sample_odoo_handoff_payload.json",
                "purpose": "Local Odoo/ERP-style handoff demonstration payload.",
                "generated_in_current_package": True,
            },
            {
                "filename": "simulation_results.csv",
                "relative_path": "future_report_bundle/simulation_results.csv",
                "purpose": "Future report-bundle attachment candidate.",
                "generated_in_current_package": False,
            },
            {
                "filename": "scenario_report.zip",
                "relative_path": "future_report_bundle/scenario_report.zip",
                "purpose": "Future reviewed report-bundle attachment candidate.",
                "generated_in_current_package": False,
            },
        ],
        "audit_trail": {
            "assumptions_preserved": True,
            "generated_at": generated,
            "validation_boundary": validation_boundary,
            "evidence_references": [
                "tests/test_integration_payload_contract.py",
                "tests/test_odoo_handoff_payload.py",
                "docs/SAFE_CLAIMS.md",
                "docs/AI_ERP_EXTENSION_ROADMAP.md",
            ],
            "source_business_summary_generated_at": business_summary.get("generated_at"),
            "no_external_calls": True,
        },
        "explicit_non_claims": list(EXPLICIT_NON_CLAIMS),
    }


def write_odoo_handoff_payload(
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    simulation_count: int = 500,
    seed: int = 12345,
    generated_at: str | None = None,
    source_commit: str | None = None,
) -> Path:
    business_summary = build_business_summary_payload(
        simulation_count=simulation_count,
        seed=seed,
        generated_at=generated_at,
    )
    payload = build_odoo_handoff_payload(
        business_summary,
        generated_at=generated_at,
        source_commit=source_commit,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
