"""Contracts and safety guards for gated Odoo connector work."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from odoo_config import OdooConnectorConfig, OdooSafetyError


class OdooConnectorMode(str, Enum):
    dry_run = "dry_run"
    read_only = "read_only"
    sandbox_write = "sandbox_write"


@dataclass(frozen=True)
class OdooJson2Request:
    """JSON-2 method-call request shape without transport behavior."""

    model: str
    method: str
    params: Mapping[str, Any] = field(default_factory=dict)
    ids: Sequence[int] | None = None
    context: Mapping[str, Any] | None = None

    @property
    def path(self) -> str:
        _validate_path_segment(self.model, "model")
        _validate_path_segment(self.method, "method")
        return f"/json/2/{self.model}/{self.method}"

    def body(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.ids is not None:
            payload["ids"] = list(self.ids)
        if self.context is not None:
            payload["context"] = dict(self.context)
        payload.update(dict(self.params))
        return payload


@dataclass(frozen=True)
class OdooJson2Response:
    status_code: int
    result: Any = None
    error: Mapping[str, Any] | None = None
    raw: Any = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300 and self.error is None


@dataclass(frozen=True)
class OdooActionResult:
    action_type: str
    status: str
    message: str
    record_id: int | None = None
    dry_run: bool = True
    live_integration: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


def ensure_write_allowed(
    config: OdooConnectorConfig,
    target_metadata: Mapping[str, Any] | None,
) -> None:
    """Block writes unless all sandbox and metadata guards pass."""

    if not config.live_enabled:
        raise OdooSafetyError("Live Odoo access is disabled.")
    if not config.live_writes_enabled:
        raise OdooSafetyError("Live Odoo writes are disabled.")
    if not config.has_sandbox_confirmation:
        raise OdooSafetyError("Sandbox confirmation is required before Odoo writes.")
    if not target_metadata or target_metadata.get("verified") is not True:
        raise OdooSafetyError("Verified target model metadata is required before writes.")


def _validate_path_segment(value: str, label: str) -> None:
    if not value or "/" in value or "\\" in value:
        raise ValueError(f"Invalid Odoo JSON-2 {label} segment.")
