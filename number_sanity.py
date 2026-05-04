from __future__ import annotations

import math
from typing import Any


NON_CLAIMS = [
    "not investment advice",
    "not production-ready",
    "not a fully validated financial product",
    "no live ERP/Odoo/MCP integration",
]


def build_number_sanity_report(context: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic caveats for strong or review-worthy dashboard outputs."""

    core_metrics = context.get("core_metrics") or {}
    supporting_metrics = context.get("supporting_metrics") or {}
    sensitivity = context.get("sensitivity") or {}

    review_flags: list[str] = []
    caveats: list[str] = []
    key_drivers: list[str] = []
    metrics_to_explain: list[str] = []
    unavailable_or_placeholder_metrics: list[str] = []
    talking_points: list[str] = []

    irr_p50 = _metric_value(core_metrics, "irr")
    npv_p50 = _metric_value(core_metrics, "npv")
    physical_occ = _metric_value(supporting_metrics, "physical_occupancy")
    economic_occ = _metric_value(supporting_metrics, "economic_occupancy")
    initial_occ = _metric_value(supporting_metrics, "initial_occupancy")
    dscr = _metric_value(core_metrics, "dscr")
    debt_yield = _metric_value(core_metrics, "debt_yield")

    if irr_p50 is not None and irr_p50 > 0.15:
        review_flags.append("P50 IRR is above 15%, so the return profile should be explained by model assumptions.")
        caveats.append("Strong returns should be tied back to occupancy, rent growth, leverage, exit cap, and refi assumptions before relying on them.")
        key_drivers.append("headline return strength")
        metrics_to_explain.append("IRR P50")

    if physical_occ is not None and initial_occ is not None and physical_occ > 0.95 and initial_occ < 0.90:
        review_flags.append("Hold-average physical occupancy is above 95% while initial occupancy is below 90%.")
        caveats.append("This likely reflects lease-up or vacancy-auto-lease mechanics rather than acquisition-date occupancy.")
        key_drivers.append("lease-up / vacancy-auto-lease mechanics")
        metrics_to_explain.extend(["initial occupancy", "physical occupancy"])

    if economic_occ is not None and economic_occ > 0.98:
        review_flags.append("Economic occupancy is near full occupancy.")
        caveats.append("Near-full economic occupancy should be reviewed against free-rent, downtime, and scheduled-contract-rent mechanics.")
        key_drivers.append("near-full economic occupancy")
        metrics_to_explain.append("economic occupancy")

    if dscr is not None and dscr > 3.0:
        review_flags.append("DSCR is above 3.0x, indicating very strong modeled debt coverage.")
        caveats.append("Very strong DSCR should be explained as a model output, not treated as standalone credit proof.")
        key_drivers.append("very strong debt coverage")
        metrics_to_explain.append("DSCR")

    if debt_yield is not None and debt_yield > 0.15:
        review_flags.append("Debt yield is above 15%, indicating a very strong lender-risk metric.")
        caveats.append("Very strong debt yield should be tied to NOI, leverage, and loan-balance assumptions.")
        key_drivers.append("very strong debt yield")
        metrics_to_explain.append("debt yield")

    material_costs = _material_prepay_costs(supporting_metrics, npv_p50)
    if material_costs:
        review_flags.append("Prepayment or defeasance costs are material in the current output.")
        caveats.append("Prepay and defeasance costs should be described as major assumptions and cash-flow drivers.")
        key_drivers.append("prepay / defeasance cost assumptions")
        metrics_to_explain.extend(material_costs)

    if _has_available_sensitivity(sensitivity):
        caveats.append("Heatmap and tornado outputs should be treated as directional scenario surfaces, not proof of full model correctness.")
        talking_points.append("Use sensitivity views to discuss direction and assumption exposure, not final validation.")

    for group_name, metrics in (("core", core_metrics), ("supporting", supporting_metrics)):
        if not isinstance(metrics, dict):
            continue
        for metric_name, metric in metrics.items():
            if isinstance(metric, dict) and not metric.get("available"):
                unavailable_or_placeholder_metrics.append(f"{group_name}.{metric_name}")

    if unavailable_or_placeholder_metrics:
        caveats.append("Unavailable metrics should be called out as not available in current context; the analyst should not invent them.")

    if not review_flags:
        review_flags.append("No high-threshold number-sanity flags were triggered from the available metrics.")

    if not key_drivers:
        key_drivers.append("available headline metrics")

    if not metrics_to_explain:
        metrics_to_explain.extend(_available_metric_names(core_metrics))

    talking_points.extend(
        [
            "Separate what the model shows from what still needs review.",
            "Explain strong outputs through assumptions and mechanics instead of celebrating them.",
            "Keep conclusions inside the demo/local-review boundary.",
        ]
    )

    return {
        "headline_assessment": _headline_assessment(review_flags),
        "key_drivers": _unique(key_drivers),
        "review_flags": _unique(review_flags),
        "caveats": _unique(caveats),
        "metrics_to_explain": _unique(metrics_to_explain),
        "unavailable_or_placeholder_metrics": _unique(unavailable_or_placeholder_metrics),
        "suggested_analyst_talking_points": _unique(talking_points),
        "non_claims": list(NON_CLAIMS),
    }


def _metric_value(metrics: dict[str, Any], metric_name: str) -> float | None:
    metric = metrics.get(metric_name)
    if not isinstance(metric, dict) or not metric.get("available"):
        return None
    for key in ("p50", "mean"):
        value = _as_finite_float(metric.get(key))
        if value is not None:
            return value
    return None


def _material_prepay_costs(supporting_metrics: dict[str, Any], npv_p50: float | None) -> list[str]:
    material: list[str] = []
    threshold = 500_000.0
    if npv_p50 is not None:
        threshold = max(threshold, abs(npv_p50) * 0.01)

    for metric_name in ("prepay_cost_total", "defeasance_cost_refi", "prepay_cost_sale"):
        value = _metric_value(supporting_metrics, metric_name)
        if value is not None and value >= threshold:
            material.append(metric_name)
    return material


def _has_available_sensitivity(sensitivity: dict[str, Any]) -> bool:
    if not isinstance(sensitivity, dict):
        return False
    return any(isinstance(item, dict) and item.get("available") for item in sensitivity.values())


def _available_metric_names(metrics: dict[str, Any]) -> list[str]:
    return [
        str(name)
        for name, metric in metrics.items()
        if isinstance(metric, dict) and metric.get("available")
    ]


def _headline_assessment(review_flags: list[str]) -> str:
    if review_flags and review_flags[0].startswith("No high-threshold"):
        return "Available outputs do not trigger the configured high-threshold sanity flags."
    return "Current outputs include strong or review-worthy values that should be explained with assumptions and caveats."


def _as_finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
