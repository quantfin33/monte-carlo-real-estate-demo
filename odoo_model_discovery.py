"""Read-only Odoo model discovery request builders.

These helpers only build metadata request shapes and validate discovered field
metadata. They do not make network calls.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from odoo_connector_contract import OdooJson2Request


DEFAULT_FIELD_ATTRIBUTES = ("string", "type", "required", "readonly", "relation")


def build_doc_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/doc"


def build_fields_get_request(
    model: str,
    attributes: Iterable[str] | None = None,
) -> OdooJson2Request:
    return OdooJson2Request(
        model=model,
        method="fields_get",
        params={"attributes": list(attributes or DEFAULT_FIELD_ATTRIBUTES)},
    )


def build_ir_model_request(model: str) -> OdooJson2Request:
    return OdooJson2Request(
        model="ir.model",
        method="search_read",
        params={
            "domain": [["model", "=", model]],
            "fields": ["id", "model", "name", "state"],
            "limit": 1,
        },
    )


def build_ir_model_fields_request(model: str) -> OdooJson2Request:
    return OdooJson2Request(
        model="ir.model.fields",
        method="search_read",
        params={
            "domain": [["model", "=", model]],
            "fields": ["name", "field_description", "ttype", "required", "readonly"],
        },
    )


def validate_required_fields(
    fields_metadata: Mapping[str, Any],
    required_fields: Iterable[str],
) -> dict[str, Any]:
    required = list(required_fields)
    missing = [field for field in required if field not in fields_metadata]
    return {
        "verified": not missing,
        "required_fields": required,
        "missing_fields": missing,
        "available_fields": sorted(str(field) for field in fields_metadata.keys()),
    }


def describe_discovery_steps(base_url: str, model: str) -> list[str]:
    return [
        f"Inspect target database documentation at {build_doc_url(base_url)}.",
        f"Call fields_get for {model} to confirm field names and types.",
        "Check ir.model and ir.model.fields metadata before planning writes.",
        "Treat CRM, project, note, and attachment mappings as candidates until "
        "the target database confirms fields and permissions.",
    ]
