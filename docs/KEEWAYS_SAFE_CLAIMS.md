# Keeways Safe Claims

Date: 2026-05-04

## Purpose

This note defines what can be stated safely to Keeways based on the clean GitHub package, included artifacts, and prior verification evidence.

## Evidence Baseline

Package-included evidence:

- `UI.py`
- `rmc_model.py`
- `README.md`
- `COMPANY_DEMO_HANDOFF.md`
- `README_UI_LAUNCH.md`
- `docs/KEEWAYS_AI_ERP_EXTENSION_ROADMAP.md`
- `docs/KEEWAYS_DEMO_SCRIPT.md`
- `docs/KEEWAYS_POSITIONING_MEMO.md`
- `docs/KEEWAYS_SAFE_CLAIMS.md`
- `artifacts/logic_report.json`
- `artifacts/wiring_report.json`
- `artifacts/integration_demo/sample_business_summary.json`
- `scripts/export_demo_business_summary.py`
- `tests/test_integration_payload_contract.py`
- `ai_context.py`
- `ai_analyst.py`
- `tests/test_ai_context.py`
- `tests/test_ai_analyst.py`

Prior full-workspace verification evidence, referenced as historical support and not all included in this package:

- `python run_tests.py smoke`: pass
- `python -m pytest tests/test_ui_session_defaults.py tests/test_ui_integration.py -q -o addopts=''`: 9 passed
- `python -m pytest tests/test_core_model.py tests/audit/test_explain_p50.py tests/audit/test_stochastic_stats_corr.py -q -o addopts=''`: 24 passed
- `python -m pytest tests/test_tornado_sensitivity.py tests/test_keeways_docs_truth.py tests/test_streamlit_apptest.py -q -o addopts=''`: 4 passed
- `python scripts/quick_sanity.py`: completed, generated `artifacts/logic_report.json`, and reports `all_pass: true`
- `python scripts/build_wiring_report.py`: completed and generated `artifacts/wiring_report.json`
- `python scripts/stress_matrix.py --out artifacts/stress_matrix --bounded`: completed with `all_pass: true`
- `python scripts/keeways_verify.py`: completed with `overall_pass: true`
- Browser gate in the verified local environment: completed with a visible 5,000-result run, model-derived Tornado chart, Heatmap 1 chart, Trace / Explain surface, and exports

Do not infer that omitted full-workspace scripts or browser artifacts are included in the clean GitHub package.

## Safe Current Claims

- This repository currently provides a Streamlit-based Monte Carlo real-estate analytics dashboard.
- The live dashboard preserves a broad business-facing workflow rather than a stripped-down demo surface.
- The app exposes simulation controls, scenario/risk inputs, IRR distribution analysis, covenant views, sensitivity visuals, exports, and a preserved Trace / Explain surface.
- The smoke path passed in the verified local environment.
- Current UI/session-default tests and current core/explainability/correlation tests passed in the verified local environment.
- A local deterministic business-summary export payload exists for future reporting or handoff-pattern discussion.
- An optional AI Analyst Chat layer can explain current simulation outputs when configured, with deterministic fallback behavior when live AI is not configured.
- Current Tornado sensitivity output is bounded and model-derived rather than hardcoded demo data.
- The bounded stress matrix passed across base, high debt, low rent growth, high OpEx, vacancy auto-lease off, and high exit-cap scenarios for seeds `42`, `123`, and `314`.
- A browser-driven default run completed with `5,000` results and rendered the main dashboard, model-derived Tornado, Heatmap 1, Trace / Explain, and exports.
- The quick sanity artifact shows monotonic P5/P50/P95 ordering for `IRR`, `NPV`, `CoC`, and `EquityMultiple`.
- The quick sanity artifact shows an exact `0.0` basis-point difference between engine IRR and recomputed trace IRR for the tested trace case.
- The quick sanity artifact did not show extreme outlier behavior such as `IRR > 100%`, `CoC > 1000%`, or runs with negative NOI in the sampled check.
- The UI now keeps advanced sections visible while using guarded placeholders and validation-state messaging instead of deleting them.

## Claims That Must Stay Qualified

- Tornado is now model-derived for the bounded low/high shock set, but it should not be described as a full institutional sensitivity suite.
- Heatmap sections are appropriate to present as directional analytics surfaces, but they should not be described as fully revalidated from end to end unless a dedicated contract pass is completed.
- Additional KPI surfaces may still rely on guarded placeholders or partial runtime coverage and should be described as preserved workflow surfaces, not as a guarantee that every historical metric contract is fully restored.
- The Trace / Explain section is now preserved and visible, but its broader export/bundle flow should still be described as under verification.
- Sale-month-dependent behavior should not be presented as fully validated timing logic.
- Wiring-report output shows that some UI parameters still do not map cleanly to engine consumers, so the repo should not yet be described as contract-complete.

## Explicit Non-Claims

Do not claim any of the following:

- live ERP, SAP, Odoo, or CRM integration
- an implemented MCP server or production AI-agent layer
- autonomous advisor, investment recommendation engine, or production AI agent
- live OpenAI or AI-agent integration beyond the optional local analyst chat boundary
- full production validation of every advanced metric and workflow surface
- that historical acceptance artifacts alone prove current runtime quality
- that every visible control currently drives a verified downstream model effect

## Remaining Truthfulness Risks

- `artifacts/wiring_report.json` still shows 15 parameters without direct engine consumers in the current contract map.
- Browser verification saw non-blocking Vega/Altair infinite-extent warnings while charts updated, even though the visible dashboard, IRR histogram, Tornado, and Heatmap 1 rendered.
- Preserved advanced surfaces improve demo completeness, but they still require careful verbal framing during external walkthroughs.
- No production deployment has been verified in this pass.

## Recommended External Framing

Use this positioning:

- “validated core dashboard with preserved advanced workflow surfaces”
- “demo-ready analytics product with current smoke, UI, and core-audit evidence”
- “future candidate for assistant-driven reporting and broader business-system workflows”

Avoid this positioning:

- “fully validated institutional underwriting engine”
- “finished explainability delivery stack”
- “already integrated into ERP or business systems”
