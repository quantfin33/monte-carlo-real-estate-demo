from __future__ import annotations

import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


CONTRACT_VERSION = "1.0"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas" / "export_contracts"

NON_CLAIMS = [
    "Not investment advice.",
    "Not production financial software.",
    "Not a fully validated institutional underwriting engine.",
    "ERP, Odoo, CRM, SAP, and MCP connectors are not implemented.",
    "No autonomous underwriting, lending, or investment workflow.",
]

SAFE_CLAIMS = [
    "Local portfolio-demo analytics workflow.",
    "Deterministic fixed-seed exports for review and audit evidence.",
    "Scenario, risk, trace, and handoff payloads are demo artifacts.",
]

CLAIM_BOUNDARIES = [
    "Local demo outputs only.",
    "No external system sync or network side effects.",
    "Scenario outputs are sensitivity review artifacts, not forecasts or advice.",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_metadata(artifact: str) -> dict[str, str]:
    return {
        "artifact": artifact,
        "source": "local_demo_bundle_generator",
        "contract_version": CONTRACT_VERSION,
    }


class ContractValidationError(ValueError):
    """Raised when a local export payload does not satisfy its JSON contract."""


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA:
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(to_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_schema(contract_name: str) -> dict[str, Any]:
    schema_path = SCHEMA_DIR / f"{contract_name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Unknown export contract schema: {contract_name}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_export_contract(contract_name: str, payload: dict[str, Any]) -> None:
    schema = load_schema(contract_name)
    _validate_node(payload, schema, path="$")
    if contract_name == "scenario_matrix":
        rows = payload.get("matrix")
        if not isinstance(rows, list) or len(rows) != 27:
            raise ContractValidationError("scenario_matrix must contain exactly 27 rows")
        probability_sum = payload.get("probabilities_sum")
        if not isinstance(probability_sum, (int, float)) or abs(float(probability_sum) - 1.0) > 1e-9:
            raise ContractValidationError("scenario_matrix probabilities_sum must equal 1.0")


def _validate_node(value: Any, schema: dict[str, Any], *, path: str) -> None:
    if "const" in schema and value != schema["const"]:
        raise ContractValidationError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractValidationError(f"{path} must be one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type and not _type_matches(value, expected_type):
        raise ContractValidationError(f"{path} must be {expected_type}, got {type(value).__name__}")

    if expected_type == "object":
        required = schema.get("required", [])
        for key in required:
            if not isinstance(value, dict) or key not in value:
                raise ContractValidationError(f"{path}.{key} is required")
        for key, child_schema in schema.get("properties", {}).items():
            if isinstance(value, dict) and key in value:
                _validate_node(value[key], child_schema, path=f"{path}.{key}")

    if expected_type == "array":
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            raise ContractValidationError(f"{path} must contain at least {schema['minItems']} items")
        child_schema = schema.get("items")
        if child_schema:
            for index, item in enumerate(value):
                _validate_node(item, child_schema, path=f"{path}[{index}]")


def _type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def metric_stats(df: pd.DataFrame, column: str) -> dict[str, float | None]:
    series = pd.to_numeric(df[column], errors="coerce").dropna() if column in df.columns else pd.Series(dtype=float)
    if series.empty:
        return {"mean": None, "p5": None, "p50": None, "p95": None}
    return {
        "mean": float(series.mean()),
        "p5": float(np.percentile(series, 5)),
        "p50": float(np.percentile(series, 50)),
        "p95": float(np.percentile(series, 95)),
    }


def first_available_stat(df: pd.DataFrame, columns: list[str], reducer: str) -> float | None:
    for column in columns:
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue
        if reducer == "min":
            return float(series.min())
        if reducer == "max":
            return float(series.max())
        return float(series.mean())
    return None


def extract_headline_metrics(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "irr": metric_stats(df, "IRR"),
        "npv": metric_stats(df, "NPV"),
        "coc": metric_stats(df, "CoC"),
        "equity_multiple": metric_stats(df, "EquityMultiple"),
        "risk": {
            "min_dscr": first_available_stat(df, ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr", "DSCR"], "min"),
            "min_debt_yield": first_available_stat(df, ["MinDebtYield", "DebtYield_Min", "DebtYield_Y1"], "min"),
            "max_ltv": first_available_stat(df, ["LTV_Max", "LTV"], "max"),
            "negative_noi_y1_count": int(
                (pd.to_numeric(df["NOI_Y1"], errors="coerce") < 0).sum()
            )
            if "NOI_Y1" in df.columns
            else 0,
        },
    }


def build_business_summary_export(
    df: pd.DataFrame,
    *,
    params: dict[str, Any],
    seed: int,
    preset: str,
    risk_flags: list[dict[str, Any]] | None = None,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return to_jsonable(
        {
            "contract_name": "business_summary",
            "contract_version": CONTRACT_VERSION,
            "source": source_metadata("business_summary"),
            "generated_at_utc": utc_now_iso(),
            "classification": "portfolio_demo",
            "seed": int(seed),
            "preset": preset,
            "inputs": params,
            "key_metrics": extract_headline_metrics(df),
            "trace": trace or {"available": False, "mode": "not_requested"},
            "risk_flags": risk_flags or [],
            "safe_claims": SAFE_CLAIMS,
            "claim_boundaries": CLAIM_BOUNDARIES,
            "non_claims": NON_CLAIMS,
            "network_calls_made": False,
        }
    )


def build_ai_context_export(business_summary: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(
        {
            "contract_name": "ai_context",
            "contract_version": CONTRACT_VERSION,
            "source": source_metadata("ai_context"),
            "generated_at_utc": business_summary["generated_at_utc"],
            "classification": "portfolio_demo_context",
            "seed": business_summary["seed"],
            "preset": business_summary["preset"],
            "source_payload": {
                "preset": business_summary["preset"],
                "key_metrics": business_summary["key_metrics"],
                "trace": business_summary["trace"],
                "risk_flags": business_summary.get("risk_flags", []),
            },
            "boundaries": [
                "Explain only the provided simulation outputs.",
                "Do not invent missing metrics, traces, screenshots, integrations, or market data.",
                "Do not provide investment, legal, tax, lending, or valuation advice.",
            ],
            "non_claims": NON_CLAIMS,
            "network_calls_made": False,
        }
    )


def build_odoo_handoff_payload(business_summary: dict[str, Any]) -> dict[str, Any]:
    metrics = business_summary["key_metrics"]
    return to_jsonable(
        {
            "contract_name": "odoo_handoff_payload",
            "contract_version": CONTRACT_VERSION,
            "source": source_metadata("odoo_handoff_payload"),
            "generated_at_utc": business_summary["generated_at_utc"],
            "handoff_mode": "local_dry_run_only",
            "classification": "portfolio_demo_handoff",
            "seed": business_summary["seed"],
            "preset": business_summary["preset"],
            "inputs": business_summary["inputs"],
            "key_metrics": metrics,
            "proposed_odoo_target": {
                "model_candidates": ["crm.lead", "project.task", "documents.document"],
                "live_integration": False,
                "connector_implemented": False,
                "external_api_used": False,
            },
            "dry_run_actions": [
                {
                    "action": "create_review_record",
                    "status": "not_executed",
                    "implemented_now": False,
                    "would_call_api": False,
                },
                {
                    "action": "attach_scenario_review_memo",
                    "status": "not_executed",
                    "implemented_now": False,
                    "would_call_api": False,
                },
            ],
            "audit": {
                "network_calls_made": False,
                "credentials_required": False,
                "payload_source": "local_demo_export",
            },
            "non_claims": NON_CLAIMS,
            "network_calls_made": False,
        }
    )
