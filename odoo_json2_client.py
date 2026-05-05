"""Gated Odoo 19 JSON-2 client.

This module is not imported by the Streamlit app or by the local dry-run mapper.
Constructing a client requires explicit sandbox live-mode configuration.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

from odoo_config import OdooConnectorConfig, OdooSafetyError, redact_secret
from odoo_connector_contract import (
    OdooJson2Request,
    OdooJson2Response,
    ensure_write_allowed,
)


USER_AGENT = "keeways-rmc-demo-odoo-connector"


class OdooJson2Error(RuntimeError):
    """Base error for Odoo JSON-2 client failures."""


class OdooJson2HttpError(OdooJson2Error):
    """Raised for non-2xx HTTP responses."""


class OdooJson2TimeoutError(OdooJson2Error):
    """Raised when an Odoo JSON-2 call times out."""


class OdooJson2BadResponseError(OdooJson2Error):
    """Raised when Odoo returns a response that cannot be parsed safely."""


class OdooJson2StructuredError(OdooJson2Error):
    """Raised when Odoo returns a structured JSON error object."""


class OdooJson2Client:
    """Minimal Odoo 19 JSON-2 client for explicitly configured sandbox probes."""

    def __init__(
        self,
        config: OdooConnectorConfig,
        *,
        opener: Any | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        config.require_live_enabled()
        self.config = config
        self._opener = opener or urllib.request.urlopen
        self._ssl_context = ssl_context

    @classmethod
    def from_env(cls) -> "OdooJson2Client":
        return cls(OdooConnectorConfig.from_env())

    def dry_run_request(
        self,
        model: str,
        method: str,
        *,
        params: Mapping[str, Any] | None = None,
        ids: Sequence[int] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = OdooJson2Request(
            model=model,
            method=method,
            params=params or {},
            ids=ids,
            context=context,
        )
        return build_json2_request_preview(
            base_url=self.config.base_url or "",
            database=self.config.database,
            api_key=self.config.api_key,
            request=request,
        )

    def call(
        self,
        model: str,
        method: str,
        *,
        params: Mapping[str, Any] | None = None,
        ids: Sequence[int] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> OdooJson2Response:
        request_shape = OdooJson2Request(
            model=model,
            method=method,
            params=params or {},
            ids=ids,
            context=context,
        )
        url = _join_url(self.config.base_url or "", request_shape.path)
        data = json.dumps(request_shape.body(), sort_keys=True).encode("utf-8")
        urllib_request = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(redacted=False),
            method="POST",
        )

        try:
            response = self._opener(
                urllib_request,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context,
            )
            with response:
                status_code = _response_status(response)
                payload = _decode_json(response.read())
        except urllib.error.HTTPError as exc:
            raise OdooJson2HttpError(_format_http_error(exc, self.config)) from exc
        except (socket.timeout, TimeoutError, urllib.error.URLError) as exc:
            raise OdooJson2TimeoutError(
                "Odoo JSON-2 request failed or timed out; check sandbox network "
                "access and credentials."
            ) from exc

        if isinstance(payload, dict) and payload.get("error") is not None:
            raise OdooJson2StructuredError(
                "Odoo JSON-2 returned an error object: "
                + _safe_json(payload.get("error"))
            )

        return OdooJson2Response(status_code=status_code, result=payload, raw=payload)

    def health_check(self) -> OdooJson2Response:
        return self.search_read("ir.model", domain=[], fields=["model"], limit=1)

    def search_read(
        self,
        model: str,
        *,
        domain: Sequence[Any] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> OdooJson2Response:
        params: dict[str, Any] = {"domain": list(domain or [])}
        if fields is not None:
            params["fields"] = list(fields)
        if limit is not None:
            params["limit"] = limit
        return self.call(model, "search_read", params=params)

    def create(
        self,
        model: str,
        values: Mapping[str, Any],
        *,
        target_metadata: Mapping[str, Any] | None,
    ) -> OdooJson2Response:
        ensure_write_allowed(self.config, target_metadata)
        return self.call(model, "create", params={"vals_list": [dict(values)]})

    def _headers(self, *, redacted: bool) -> dict[str, str]:
        api_key = self.config.api_key or ""
        auth_secret = redact_secret(api_key) if redacted else api_key
        headers = {
            "Authorization": f"bearer {auth_secret}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": USER_AGENT,
        }
        if self.config.database:
            headers["X-Odoo-Database"] = self.config.database
        return headers


def build_json2_request_preview(
    *,
    base_url: str,
    database: str | None,
    api_key: str | None,
    request: OdooJson2Request,
) -> dict[str, Any]:
    """Build a redacted JSON-2 request preview without opening a network socket."""

    headers = {
        "Authorization": f"bearer {redact_secret(api_key)}",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": USER_AGENT,
    }
    if database:
        headers["X-Odoo-Database"] = database
    return {
        "method": "POST",
        "url": _join_url(base_url, request.path) if base_url else request.path,
        "path": request.path,
        "headers": headers,
        "json_body": request.body(),
        "network_calls_made": False,
    }


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _decode_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OdooJson2BadResponseError("Odoo JSON-2 response was not valid JSON.") from exc


def _response_status(response: Any) -> int:
    if hasattr(response, "getcode"):
        return int(response.getcode())
    return int(getattr(response, "status", 200))


def _format_http_error(exc: urllib.error.HTTPError, config: OdooConnectorConfig) -> str:
    try:
        raw = exc.read()
        body = _safe_json(json.loads(raw.decode("utf-8"))) if raw else ""
    except Exception:
        body = "<unreadable response>"
    return (
        f"Odoo JSON-2 HTTP error {exc.code}. "
        f"base_url={config.base_url!r}, api_key={redact_secret(config.api_key)}, "
        f"body={body}"
    )


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return repr(value)
