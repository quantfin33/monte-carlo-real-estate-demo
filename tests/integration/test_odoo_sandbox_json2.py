import os

import pytest

from odoo_config import OdooConnectorConfig
from odoo_json2_client import OdooJson2Client
from odoo_model_discovery import build_fields_get_request


pytestmark = pytest.mark.integration


def _sandbox_env_ready() -> bool:
    if os.environ.get("ODOO_LIVE_ENABLED") != "true":
        return False
    return all(
        os.environ.get(name)
        for name in (
            "ODOO_BASE_URL",
            "ODOO_DATABASE",
            "ODOO_API_KEY",
            "ODOO_SANDBOX_CONFIRMATION",
        )
    )


@pytest.mark.skipif(
    not _sandbox_env_ready(),
    reason="Odoo sandbox env vars are not configured; skipping live read-only probe.",
)
def test_odoo_sandbox_read_only_fields_get_probe():
    config = OdooConnectorConfig.from_env()
    config.require_database()
    client = OdooJson2Client(config)
    request = build_fields_get_request(os.environ.get("ODOO_TARGET_MODEL", "project.task"))

    response = client.call(
        request.model,
        request.method,
        params=request.params,
        ids=request.ids,
        context=request.context,
    )

    assert response.ok is True


@pytest.mark.skipif(
    os.environ.get("ODOO_ENABLE_LIVE_WRITES") != "true"
    or os.environ.get("PYTEST_ODOO_ALLOW_SANDBOX_WRITE") != "true",
    reason="Sandbox write probe requires explicit env flags and is skipped by default.",
)
def test_odoo_sandbox_write_probe_is_not_enabled_in_this_phase():
    pytest.skip("Sandbox write execution is intentionally not implemented in this phase.")
