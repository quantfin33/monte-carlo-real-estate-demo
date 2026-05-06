# Workflow Product Roadmap

This roadmap separates implemented local demo artifacts from future workflow-product directions. It should be read together with `docs/KEEWAYS_SAFE_CLAIMS.md`.

## Implemented Now

- Streamlit Monte Carlo analytics dashboard.
- Deterministic local evidence bundle via `scripts/generate_demo_bundle.py`.
- Schema-validated JSON contracts for business summary, AI context, Odoo handoff payload, scenario matrix, and risk flags.
- 27-case demo sensitivity matrix for rent growth, expense growth, and exit cap rate.
- Structured risk flags for DSCR, debt yield, LTV, downside percentile, negative cashflow, and volatility.
- Scenario Review Memo export.
- Local dry-run Odoo handoff payload shape with `network_calls_made=false`.

## Sandbox / Dry-Run Only

- Odoo/ERP handoff payloads are local JSON artifacts.
- Dry-run actions describe what a future connector might map, but no external API call is made.
- AI context exports are bounded prompt/context payloads, not autonomous agent execution.

## Future Only

- JSON/CSV input upload and normalization.
- Odoo sandbox connector proof.
- Hosted multi-user deployment.
- Live ERP, CRM, SAP, or MCP integration.
- AI-assisted underwriting/reporting workflow tied to validated payloads.

## Claim Boundary

Safe phrasing:

- "portfolio-demo analytics workflow"
- "deterministic local evidence bundle"
- "schema-validated dry-run handoff payload"
- "future candidate for workflow integration"

Avoid phrasing:

- "institutional underwriting platform"
- "live ERP connector already working"
- "autonomous deal-decision system"
- "replacement for ARGUS or Dealpath"
