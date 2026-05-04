from __future__ import annotations

from number_sanity import build_number_sanity_report


def _strong_context() -> dict:
    return {
        "core_metrics": {
            "irr": {"available": True, "unit": "decimal_rate", "p50": 0.1732},
            "npv": {"available": True, "unit": "dollars", "p50": 35_460_000.0},
            "dscr": {"available": True, "unit": "ratio", "p50": 4.39},
            "debt_yield": {"available": True, "unit": "decimal_rate", "p50": 0.2966},
            "ltv": {"available": False, "unit": "decimal_rate"},
        },
        "supporting_metrics": {
            "initial_occupancy": {"available": True, "unit": "decimal_rate", "p50": 0.826},
            "physical_occupancy": {"available": True, "unit": "decimal_rate", "p50": 0.9988},
            "economic_occupancy": {"available": True, "unit": "decimal_rate", "p50": 1.0},
            "prepay_cost_total": {"available": True, "unit": "dollars", "p50": 1_250_000.0},
            "defeasance_cost_refi": {"available": True, "unit": "dollars", "p50": 2_000_000.0},
            "prepay_cost_sale": {"available": True, "unit": "dollars", "p50": 800_000.0},
        },
        "sensitivity": {
            "heatmap_1": {"available": True, "label": "Heatmap 1"},
            "heatmap_2": {"available": False, "label": "Heatmap 2"},
            "tornado": {"available": True, "label": "Tornado"},
        },
    }


def _report_text(report: dict) -> str:
    return "\n".join(
        str(item)
        for key in (
            "headline_assessment",
            "key_drivers",
            "review_flags",
            "caveats",
            "metrics_to_explain",
            "unavailable_or_placeholder_metrics",
            "suggested_analyst_talking_points",
            "non_claims",
        )
        for item in (report.get(key) if isinstance(report.get(key), list) else [report.get(key)])
    )


def test_strong_irr_triggers_assumption_review_caveat():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "p50 irr is above 15%" in text
    assert "assumptions" in text


def test_high_physical_occupancy_vs_lower_initial_occupancy_is_flagged():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "physical occupancy is above 95%" in text
    assert "initial occupancy is below 90%" in text
    assert "lease-up" in text


def test_high_economic_occupancy_is_flagged():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "economic occupancy is near full occupancy" in text


def test_high_dscr_and_debt_yield_are_flagged():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "dscr is above 3.0x" in text
    assert "debt yield is above 15%" in text


def test_material_prepay_and_defeasance_costs_are_flagged():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "prepayment or defeasance costs are material" in text
    assert "prepay_cost_total" in report["metrics_to_explain"]
    assert "defeasance_cost_refi" in report["metrics_to_explain"]
    assert "prepay_cost_sale" in report["metrics_to_explain"]


def test_sensitivity_metadata_adds_directional_caveat():
    report = build_number_sanity_report(_strong_context())
    text = _report_text(report).lower()

    assert "directional scenario surfaces" in text
    assert "not proof of full model correctness" in text


def test_missing_metrics_do_not_crash_and_produce_unavailable_warning():
    report = build_number_sanity_report(
        {
            "core_metrics": {
                "irr": {"available": True, "p50": 0.10, "unit": "decimal_rate"},
                "npv": {"available": False, "unit": "dollars"},
            },
            "supporting_metrics": {
                "physical_occupancy": {"available": False, "unit": "decimal_rate"},
            },
        }
    )

    assert "core.npv" in report["unavailable_or_placeholder_metrics"]
    assert "supporting.physical_occupancy" in report["unavailable_or_placeholder_metrics"]
    assert any("should not invent" in caveat for caveat in report["caveats"])


def test_non_claims_are_preserved():
    report = build_number_sanity_report(_strong_context())
    non_claims = "\n".join(report["non_claims"])

    assert "not investment advice" in non_claims
    assert "not production-ready" in non_claims
    assert "not a fully validated financial product" in non_claims
    assert "no live ERP/Odoo/MCP integration" in non_claims
