import pytest

from odoo_config import (
    OdooConfigError,
    OdooConnectorConfig,
    OdooSafetyError,
    parse_exact_true,
    redact_secret,
)


def test_config_defaults_fail_closed():
    config = OdooConnectorConfig.from_mapping({})

    assert config.live_enabled is False
    assert config.live_writes_enabled is False
    assert config.api_key is None


def test_exact_true_only():
    assert parse_exact_true("true") is True
    assert parse_exact_true("True") is False
    assert parse_exact_true("1") is False
    assert parse_exact_true(True) is False


def test_missing_env_blocks_live_mode():
    with pytest.raises(OdooConfigError, match="Missing required"):
        OdooConnectorConfig.from_mapping({"ODOO_LIVE_ENABLED": "true"})


def test_live_writes_require_live_mode():
    with pytest.raises(OdooSafetyError, match="requires ODOO_LIVE_ENABLED"):
        OdooConnectorConfig.from_mapping({"ODOO_ENABLE_LIVE_WRITES": "true"})


def test_api_key_redaction():
    assert redact_secret("abcdef123456") == "****3456"
    assert redact_secret("abcd") == "****"
    assert redact_secret(None) == "****"


def test_invalid_sandbox_confirmation_aborts_live_mode():
    with pytest.raises(OdooSafetyError, match="must explicitly identify"):
        OdooConnectorConfig.from_mapping(
            {
                "ODOO_LIVE_ENABLED": "true",
                "ODOO_BASE_URL": "https://company.example.test",
                "ODOO_API_KEY": "test_secret_123456",
                "ODOO_SANDBOX_CONFIRMATION": "real environment",
            }
        )


def test_live_config_uses_redacted_dict():
    config = OdooConnectorConfig.from_mapping(
        {
            "ODOO_LIVE_ENABLED": "true",
            "ODOO_BASE_URL": "https://sandbox.example.test",
            "ODOO_DATABASE": "demo_sandbox_db",
            "ODOO_API_KEY": "test_secret_123456",
            "ODOO_SANDBOX_CONFIRMATION": "sandbox",
        }
    )

    redacted = config.redacted_dict()
    assert redacted["api_key"] == "****3456"
    assert "test_secret" not in str(redacted)
