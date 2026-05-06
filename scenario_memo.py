from __future__ import annotations

from typing import Any

from export_contracts import NON_CLAIMS


def render_scenario_review_memo(
    *,
    business_summary: dict[str, Any],
    scenario_matrix: list[dict[str, Any]],
    risk_flags: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> str:
    metrics = business_summary["key_metrics"]
    risk = metrics["risk"]
    lines = [
        "# Scenario Review Memo",
        "",
        "## Scope",
        "",
        "This memo summarizes a local portfolio-demo simulation export. It is a deterministic review artifact for discussing assumptions, sensitivity, risk flags, trace availability, and handoff payload shape.",
        "",
        "## Run Identity",
        "",
        f"- Preset: `{business_summary['preset']}`",
        f"- Seed: `{business_summary['seed']}`",
        f"- Classification: `{business_summary['classification']}`",
        f"- Network calls made: `{business_summary['network_calls_made']}`",
        "",
        "## Headline Metrics",
        "",
        "| Metric | Mean | P5 | P50 | P95 |",
        "|---|---:|---:|---:|---:|",
        _metric_row("IRR", metrics["irr"], pct=True),
        _metric_row("NPV", metrics["npv"], money=True),
        _metric_row("Cash-on-Cash", metrics["coc"], pct=True),
        _metric_row("Equity Multiple", metrics["equity_multiple"], suffix="x"),
        "",
        "## Covenant And Risk Snapshot",
        "",
        f"- Minimum DSCR observed: `{_fmt(risk.get('min_dscr'))}`",
        f"- Minimum debt yield observed: `{_fmt(risk.get('min_debt_yield'), pct=True)}`",
        f"- Maximum LTV observed: `{_fmt(risk.get('max_ltv'), pct=True)}`",
        f"- Negative Year 1 NOI count: `{risk.get('negative_noi_y1_count', 0)}`",
        "",
        "## 27-Case Demo Sensitivity Matrix",
        "",
        "The matrix varies rent growth, expense growth, and exit cap rate across downside, base, and upside states. It is labeled as demo sensitivity, not a forecast.",
        "",
        "| Scenario | Probability | IRR Mean | IRR P5 | Min DSCR | Max LTV |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in scenario_matrix:
        row_metrics = row["metrics"]
        row_risk = row_metrics["risk"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['scenario_id']}`",
                    _fmt(row["probability"], pct=True),
                    _fmt(row_metrics["irr"]["mean"], pct=True),
                    _fmt(row_metrics["irr"]["p5"], pct=True),
                    _fmt(row_risk.get("min_dscr")),
                    _fmt(row_risk.get("max_ltv"), pct=True),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Structured Risk Flags",
            "",
            "| Severity | Category | Metric | Threshold | Observed | Evidence |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    if risk_flags:
        for flag in risk_flags:
            lines.append(
                "| "
                + " | ".join(
                    [
                        flag["severity"],
                        flag["category"],
                        flag["metric"],
                        _fmt(flag["threshold"]),
                        _fmt(flag["observed_value"]),
                        flag["evidence_source"],
                    ]
                )
                + " |"
            )
    else:
        lines.append("| INFO | none | none |  |  | simulation_results |")

    lines.extend(
        [
            "",
            "## Trace And Evidence",
            "",
            f"- Trace available: `{business_summary['trace'].get('available', False)}`",
            f"- Trace mode: `{business_summary['trace'].get('mode', 'not_requested')}`",
        ]
    )
    if manifest:
        lines.append(f"- Bundle id: `{manifest.get('bundle_id')}`")
        lines.append(f"- Generated files: `{len(manifest.get('generated_files', []))}`")

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
        ]
    )
    for claim in NON_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    return "\n".join(lines)


def _metric_row(label: str, stats: dict[str, Any], *, pct: bool = False, money: bool = False, suffix: str = "") -> str:
    return (
        f"| {label} | {_fmt(stats.get('mean'), pct=pct, money=money, suffix=suffix)} "
        f"| {_fmt(stats.get('p5'), pct=pct, money=money, suffix=suffix)} "
        f"| {_fmt(stats.get('p50'), pct=pct, money=money, suffix=suffix)} "
        f"| {_fmt(stats.get('p95'), pct=pct, money=money, suffix=suffix)} |"
    )


def _fmt(value: Any, *, pct: bool = False, money: bool = False, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if pct:
        return f"{numeric:.2%}"
    if money:
        return f"${numeric:,.0f}"
    if suffix:
        return f"{numeric:.2f}{suffix}"
    return f"{numeric:.3f}"

