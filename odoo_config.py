"""Strict, fail-closed configuration for future Odoo sandbox connectors.

The existing Odoo handoff payload and dry-run mapper do not use this module.
This module is only for explicitly configured sandbox probes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


class OdooConfigError(ValueError):
    """Raised when required Odoo connector configuration is missing or invalid."""


class OdooSafetyError(RuntimeError):
    """Raised when Odoo connector safety guards block execution."""


TRUE_VALUE = "true"
SANDBOX_CONFIRMATION_TERMS = (
    "sandbox",
    "staging",
    "test",
    "dev",
    "non-production",
    "nonproduction",
    "nonprod",
    "qa",
)


def parse_exact_true(value: object) -> bool:
    """Return true only for the exact string required by the safety contract."""

    return value == TRUE_VALUE


def redact_secret(value: object) -> str:
    """Redact a secret as ****last4 without exposing the original value."""

    if value is None:
        return "****"
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"****{text[-4:]}"


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_sandbox_confirmation(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return any(term in normalized for term in SANDBOX_CONFIRMATION_TERMS)


def _host_looks_sandbox(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.lower()
    return any(term in normalized for term in SANDBOX_CONFIRMATION_TERMS)


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise OdooSafetyError("ODOO_BASE_URL must use https for live sandbox probes.")
    if not parsed.netloc:
        raise OdooConfigError("ODOO_BASE_URL must include a host.")
    if parsed.username or parsed.password:
        raise OdooSafetyError("ODOO_BASE_URL must not include credentials.")


@dataclass(frozen=True)
class OdooConnectorConfig:
    """Configuration object for gated Odoo JSON-2 sandbox access."""

    live_enabled: bool = False
    live_writes_enabled: bool = False
    base_url: str | None = None
    database: str | None = None
    api_key: str | None = None
    login: str | None = None
    target_model: str | None = None
    target_record_id: str | None = None
    test_project_id: str | None = None
    sandbox_confirmation: str | None = None
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "OdooConnectorConfig":
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "OdooConnectorConfig":
        live_enabled = parse_exact_true(mapping.get("ODOO_LIVE_ENABLED"))
        live_writes_enabled = parse_exact_true(mapping.get("ODOO_ENABLE_LIVE_WRITES"))

        if live_writes_enabled and not live_enabled:
            raise OdooSafetyError(
                "ODOO_ENABLE_LIVE_WRITES=true requires ODOO_LIVE_ENABLED=true."
            )

        timeout_seconds = _parse_timeout(mapping.get("ODOO_TIMEOUT_SECONDS"))
        config = cls(
            live_enabled=live_enabled,
            live_writes_enabled=live_writes_enabled,
            base_url=_clean(mapping.get("ODOO_BASE_URL")),
            database=_clean(mapping.get("ODOO_DATABASE")),
            api_key=_clean(mapping.get("ODOO_API_KEY")),
            login=_clean(mapping.get("ODOO_LOGIN")),
            target_model=_clean(mapping.get("ODOO_TARGET_MODEL")),
            target_record_id=_clean(mapping.get("ODOO_TARGET_RECORD_ID")),
            test_project_id=_clean(mapping.get("ODOO_TEST_PROJECT_ID")),
            sandbox_confirmation=_clean(mapping.get("ODOO_SANDBOX_CONFIRMATION")),
            timeout_seconds=timeout_seconds,
        )

        if config.live_enabled:
            config._validate_live_readiness()
        return config

    @property
    def has_sandbox_confirmation(self) -> bool:
        return _has_sandbox_confirmation(self.sandbox_confirmation)

    @property
    def base_url_looks_sandbox(self) -> bool:
        if not self.base_url:
            return False
        return _host_looks_sandbox(urlparse(self.base_url).hostname)

    def require_live_enabled(self) -> None:
        if not self.live_enabled:
            raise OdooSafetyError(
                "Odoo live access is disabled. Set ODOO_LIVE_ENABLED=true for "
                "explicit sandbox probes."
            )
        self._validate_live_readiness()

    def require_database(self) -> None:
        if not self.database:
            raise OdooConfigError("ODOO_DATABASE is required for this sandbox probe.")

    def redacted_dict(self) -> dict[str, object]:
        return {
            "live_enabled": self.live_enabled,
            "live_writes_enabled": self.live_writes_enabled,
            "base_url": self.base_url,
            "database": self.database,
            "api_key": redact_secret(self.api_key) if self.api_key else None,
            "login": self.login,
            "target_model": self.target_model,
            "target_record_id": self.target_record_id,
            "test_project_id": self.test_project_id,
            "sandbox_confirmation": bool(self.sandbox_confirmation),
            "timeout_seconds": self.timeout_seconds,
        }

    def _validate_live_readiness(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("ODOO_BASE_URL")
        if not self.api_key:
            missing.append("ODOO_API_KEY")
        if not self.sandbox_confirmation:
            missing.append("ODOO_SANDBOX_CONFIRMATION")
        if missing:
            raise OdooConfigError(
                "Missing required Odoo sandbox configuration: " + ", ".join(missing)
            )

        assert self.base_url is not None
        _validate_base_url(self.base_url)

        if not self.has_sandbox_confirmation:
            raise OdooSafetyError(
                "ODOO_SANDBOX_CONFIRMATION must explicitly identify a sandbox, "
                "test, staging, dev, QA, or non-production environment."
            )


def _parse_timeout(value: object) -> float:
    if value in (None, ""):
        return 15.0
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OdooConfigError("ODOO_TIMEOUT_SECONDS must be a positive number.") from exc
    if parsed <= 0:
        raise OdooConfigError("ODOO_TIMEOUT_SECONDS must be greater than zero.")
    return parsed
