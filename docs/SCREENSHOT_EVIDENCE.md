# Screenshot Evidence

These screenshots were captured from the actual local Streamlit app, not mocked image assets. They are intended to help reviewers quickly see the working dashboard surfaces before running the project themselves.

## Evidence Table

| Screenshot | What it proves | File |
| --- | --- | --- |
| KPI / IRR results | Simulation outputs render after a run, including IRR, NPV, cash-on-cash, equity multiple, and covenant-style KPI surfaces | `screenshots/portfolio_irr_kpi_results.png` |
| Heatmap | Sensitivity visualization renders after building Heatmap 1 | `screenshots/portfolio_heatmap_sensitivity.png` |
| Tornado | Model-derived tornado chart and table render after building the tornado view | `screenshots/portfolio_tornado_sensitivity.png` |
| Smart Scenario Generator | The generator creates a pending scenario and shows old-value to new-value assumption changes before apply/run | `screenshots/portfolio_smart_scenario_generator.png` |
| AI Analyst | The explanation/chat surface works in fallback/demo analyst mode | `screenshots/portfolio_ai_analyst_chat.png` |

## Capture Method

- App launched with the local Streamlit UI on `http://127.0.0.1:8503`.
- Browser automation used Playwright from a temporary script outside the repository with local Chrome.
- `OPENAI_API_KEY` was unset so the AI Analyst screenshot shows fallback/demo analyst mode.
- The simulation screenshot used a low practical workload: `Simulations=200`, `Seed=123`.
- The Smart Scenario Generator screenshot used the `Downside` profile with generator seed `42`.
- Heatmap and tornado screenshots were captured after triggering the relevant Streamlit buttons from the running app.
- Screenshots were captured by scrolling Streamlit's `section.stMain` container to the relevant visible section.
- No production Odoo/ERP call, Odoo write, OpenAI live request, secret-bearing environment, or generated credential artifact was used for screenshot capture.

## Boundary

This evidence shows that the visible local portfolio demo surfaces render and respond in the tested paths. It does not prove production financial validation, investment suitability, hosted deployment readiness, or production ERP/Odoo/MCP/SAP integration.
