import io
import json
import urllib.error

import pytest

from odoo_config import OdooConnectorConfig, OdooSafetyError
from odoo_connector_contract import OdooJson2Request
from odoo_json2_client import (
    OdooJson2Client,
    OdooJson2HttpError,
    build_json2_request_preview,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def getcode(self):
        return self.status


def _config() -> OdooConnectorConfig:
    return OdooConnectorConfig.from_mapping(
        {
            "ODOO_LIVE_ENABLED": "true",
            "ODOO_BASE_URL": "https://sandbox.example.test",
            "ODOO_DATABASE": "demo_sandbox_db",
            "ODOO_API_KEY": "test_secret_123456",
            "ODOO_SANDBOX_CONFIRMATION": "sandbox",
        }
    )


def test_client_construction_fails_when_disabled():
    with pytest.raises(OdooSafetyError, match="disabled"):
        OdooJson2Client(OdooConnectorConfig.from_mapping({}))


def test_request_preview_builds_redacted_json2_shape():
    request = OdooJson2Request(
        model="project.task",
        method="search_read",
        params={"domain": [], "fields": ["name"], "limit": 1},
    )

    preview = build_json2_request_preview(
        base_url="https://sandbox.example.test",
        database="demo_sandbox_db",
        api_key="test_secret_123456",
        request=request,
    )

    assert preview["url"] == "https://sandbox.example.test/json/2/project.task/search_read"
    assert preview["path"] == "/json/2/project.task/search_read"
    assert preview["headers"]["Authorization"] == "bearer ****3456"
    assert preview["headers"]["X-Odoo-Database"] == "demo_sandbox_db"
    assert preview["json_body"]["fields"] == ["name"]
    assert preview["network_calls_made"] is False
    assert "test_secret" not in json.dumps(preview)


def test_dry_run_request_does_not_call_network():
    def fail_if_called(*args, **kwargs):
        raise AssertionError("network should not be called")

    client = OdooJson2Client(_config(), opener=fail_if_called)

    preview = client.dry_run_request(
        "project.task",
        "search_read",
        params={"domain": [], "fields": ["name"], "limit": 1},
    )

    assert preview["path"] == "/json/2/project.task/search_read"
    assert preview["network_calls_made"] is False


def test_call_uses_mocked_transport_and_correct_request_shape():
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse([{"id": 1, "name": "Test"}])

    client = OdooJson2Client(_config(), opener=fake_urlopen)
    response = client.search_read(
        "project.task",
        domain=[],
        fields=["name"],
        limit=1,
    )

    assert response.ok is True
    assert response.result == [{"id": 1, "name": "Test"}]
    assert captured["url"] == "https://sandbox.example.test/json/2/project.task/search_read"
    assert captured["headers"]["Authorization"] == "bearer test_secret_123456"
    assert captured["headers"]["X-odoo-database"] == "demo_sandbox_db"
    assert captured["body"] == {"domain": [], "fields": ["name"], "limit": 1}
    assert captured["timeout"] == 15.0


def test_http_errors_redact_api_key():
    def fake_urlopen(request, timeout=None, context=None):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"error": {"message": "denied"}}'),
        )

    client = OdooJson2Client(_config(), opener=fake_urlopen)

    with pytest.raises(OdooJson2HttpError) as exc_info:
        client.search_read("project.task", domain=[], fields=["name"], limit=1)

    message = str(exc_info.value)
    assert "****3456" in message
    assert "test_secret" not in message
