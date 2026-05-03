from __future__ import annotations

import json
import re

from scripts.export_demo_business_summary import write_business_summary


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return "\n".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value)


def test_business_summary_payload_contract(tmp_path):
    output_path = tmp_path / "sample_business_summary.json"

    write_business_summary(
        output_path=output_path,
        simulation_count=80,
        seed=12345,
        generated_at="2026-05-04T00:00:00Z",
    )

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    required_top_level = {
        "generated_at",
        "package_metadata",
        "scenario",
        "core_metrics",
        "risk_flags",
        "validation_boundary",
        "intended_future_targets",
        "non_claims",
    }
    assert required_top_level.issubset(payload)

    metrics = payload["core_metrics"]
    assert {"p5", "p50", "p95"}.issubset(metrics["irr"])
    for name in ["npv", "cash_on_cash", "equity_multiple", "dscr", "debt_yield", "ltv", "exit_cap"]:
        assert "p50" in metrics[name], f"Missing p50 for {name}"
        assert isinstance(metrics[name]["p50"], float)

    boundary = payload["validation_boundary"]
    assert boundary["visual_demo_ready"] is True
    assert boundary["annual_model_core_validated"] is True
    for key in [
        "live_erp_integration",
        "live_odoo_integration",
        "live_crm_integration",
        "live_sap_integration",
        "live_mcp_server",
        "openai_agent_integration",
        "hosted_release",
    ]:
        assert boundary[key] is False

    combined_text = _flatten_text(payload).lower()
    assert "openai_api_key" not in combined_text
    assert "api key" not in combined_text
    assert "/users/chris" not in combined_text
    assert "desktop/backups" not in combined_text
    assert not re.search(r"https?://", combined_text)

    forbidden_positive_claims = [
        "production-ready",
        "fully validated financial product",
        "odoo integration is implemented",
        "erp integration is implemented",
        "mcp server is implemented",
        "deployed erp workflow",
    ]
    for phrase in forbidden_positive_claims:
        assert phrase not in combined_text

    allowed_negative_claims = [
        "live odoo integration is not included",
        "autonomous investment advice is not included",
    ]
    for phrase in ["live odoo integration", "autonomous investment advice"]:
        if phrase in combined_text:
            assert any(allowed in combined_text for allowed in allowed_negative_claims)
