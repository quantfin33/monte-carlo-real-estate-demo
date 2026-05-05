import pytest
from pathlib import Path

from odoo_config import OdooConnectorConfig, OdooSafetyError
from odoo_connector_contract import (
    OdooConnectorMode,
    OdooJson2Request,
    ensure_write_allowed,
)


def _live_config(*, writes: bool = False) -> OdooConnectorConfig:
    return OdooConnectorConfig.from_mapping(
        {
            "ODOO_LIVE_ENABLED": "true",
            "ODOO_ENABLE_LIVE_WRITES": "true" if writes else "false",
            "ODOO_BASE_URL": "https://sandbox.example.test",
            "ODOO_API_KEY": "test_secret_123456",
            "ODOO_SANDBOX_CONFIRMATION": "sandbox",
        }
    )


def test_connector_modes_are_explicit():
    assert OdooConnectorMode.dry_run.value == "dry_run"
    assert OdooConnectorMode.read_only.value == "read_only"
    assert OdooConnectorMode.sandbox_write.value == "sandbox_write"


def test_json2_request_path_and_body():
    request = OdooJson2Request(
        model="project.task",
        method="search_read",
        params={"domain": [], "fields": ["name"]},
        ids=[1, 2],
        context={"lang": "en_US"},
    )

    assert request.path == "/json/2/project.task/search_read"
    assert request.body() == {
        "ids": [1, 2],
        "context": {"lang": "en_US"},
        "domain": [],
        "fields": ["name"],
    }


def test_json2_request_rejects_bad_path_segments():
    with pytest.raises(ValueError, match="Invalid"):
        _ = OdooJson2Request(model="../project.task", method="search_read").path


def test_write_guard_blocks_disabled_config():
    with pytest.raises(OdooSafetyError, match="disabled"):
        ensure_write_allowed(OdooConnectorConfig.from_mapping({}), {"verified": True})


def test_write_guard_blocks_when_write_flag_is_false():
    with pytest.raises(OdooSafetyError, match="writes are disabled"):
        ensure_write_allowed(_live_config(writes=False), {"verified": True})


def test_write_guard_blocks_missing_target_metadata():
    with pytest.raises(OdooSafetyError, match="metadata"):
        ensure_write_allowed(_live_config(writes=True), None)


def test_write_guard_allows_only_explicit_sandbox_write_with_verified_metadata():
    ensure_write_allowed(_live_config(writes=True), {"verified": True})


def test_existing_dry_run_modules_do_not_import_connector_modules():
    repo_root = Path(__file__).resolve().parents[1]
    dry_run_sources = [
        repo_root / "odoo_handoff_mapper.py",
        repo_root / "scripts" / "odoo_handoff_dry_run.py",
    ]
    forbidden_imports = (
        "odoo_config",
        "odoo_connector_contract",
        "odoo_json2_client",
        "odoo_model_discovery",
        "urllib",
        "socket",
    )

    for source_path in dry_run_sources:
        source = source_path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in source
