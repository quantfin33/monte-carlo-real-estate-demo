# Company Demo Handoff

## What This Project Is

This repository contains a Streamlit-based Monte Carlo real-estate investment analytics dashboard. It is suitable today as a visual demo and portfolio project for underwriting-style scenario analysis, risk inspection, sensitivity review, and exportable reporting.

The current audited claim boundary is:

- visual demo ready
- validated annual-model core
- intended for demo and local review, not for hosted release use
- broader end-to-end product validation remains incomplete

The package includes a local integration-ready export payload as a future handoff pattern, but no live business-system or agent integration is claimed.

The current export payload is the bridge point for future Odoo/ERP workflow integration, but no live integration is implemented.

The package also includes an AI Analyst layer for explaining current simulation outputs and surfacing number-sanity caveats, while keeping integrations and investment advice outside the claim boundary.

## What Is Verified Now

Based on the current handoff verification materials prepared for this package:

- the app launches locally from the verified virtual environment
- the smoke path passes
- current core-model tests pass
- current engine output contract tests pass
- current trace payload and explainability tests pass
- the main demo path is suitable for screenshots and live walkthroughs
- Heatmap 1, Tornado, Heatmap 2, Trace / Explain, and exports remain visible in the product

## What Is Preserved But Still Qualified

Some richer UI surfaces are intentionally preserved because they matter to the workflow story, but they should still be described carefully:

- advanced KPI groups may still rely on guarded placeholders or partial runtime coverage
- sensitivity views are appropriate as directional decision-support surfaces
- Trace / Explain is visible and materially restored at the engine level, but it should not be described as a finished explainability delivery stack
- `sale_month` remains outside the safe claim boundary and should not be presented as validated timing-aware analytics

## Exact Local Run Commands

Use the verified local environment:

```bash
source .venv/bin/activate
python run_ui.py
```

Smoke check:

```bash
source .venv/bin/activate
python run_tests.py smoke
```

When the app starts, use the local URL printed by Streamlit.

## Included Package Structure

The clean handoff package should center on:

- `README.md`
- `README_UI_LAUNCH.md`
- `COMPANY_DEMO_HANDOFF.md`
- `UI.py`
- `rmc_model.py`
- `engine_output_contract.py`
- `trace_tools.py`
- `ui_metrics.py`
- `metrics_schema.py`
- `metrics_utils.py`
- `metrics_registry.py`
- `run_ui.py`
- `run_ui.sh`
- `run.sh`
- `run_tests.py`
- `scripts/export_demo_business_summary.py`
- `pyproject.toml`
- `requirements.txt`
- `requirements_testing.txt`
- `.streamlit/`
- `docs/`
- `tests/`
- `screenshots/`
- `artifacts/logic_report.json`
- `artifacts/wiring_report.json`
- `artifacts/integration_demo/sample_business_summary.json`

## Screenshots Included

The curated `screenshots/` folder should contain:

- `keeways-review-home.png`
- `keeways-review-home-after-load.png`
- `keeways-review-after-run.png`

## Private GitHub Review Note

This repository is expected to start as a private GitHub portfolio repo. If it is shared while private, each reviewer needs collaborator access before the link will open. If the repo is made public later, verify that `README.md` and the embedded screenshots render correctly before sending it.

## Known Limitations

- this package is intended for demo and local review rather than hosted release use
- some advanced workflow surfaces remain visible with qualified wording rather than full end-to-end revalidation
- `sale_month` is still excluded from safe company-facing claims
- hosted release security and release readiness have not been established

## Explicit Non-Claims

Do not claim any of the following:

- ready for hosted release use
- complete validation of every financial workflow
- validated intra-year timing support
- business-system or assistant-workflow integrations already shipped
- proof that every visible control has a verified downstream model effect

## Safe Company-Facing Claim

This project is a polished Monte Carlo real-estate analytics dashboard with a validated annual-model core, preserved advanced workflow surfaces, current demo evidence, and a possible future path toward deeper reporting or business-system workflows.
