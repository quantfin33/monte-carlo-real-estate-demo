# Demo Script

Date: 2026-05-03

## Goal

Deliver a concise portfolio walkthrough that shows the product as a serious analytics dashboard with preserved advanced surfaces and disciplined claim boundaries.

## Launch Path

Recommended local launch from the verified environment:

```bash
source .venv/bin/activate
python run_ui.py
```

## Two-Minute Flow

### 1. Open with Product Framing

State the product clearly:

- This is a Monte Carlo real-estate analytics dashboard, not a single-case spreadsheet.
- It is designed to support underwriting-style scenario testing, risk inspection, and exportable reporting.

### 2. Show Breadth of Inputs

Use the top portion of the dashboard to show that the product covers more than basic property inputs:

- property and rent assumptions
- lease and recovery assumptions
- debt and refinance controls
- tax, reserves, and prepayment logic
- correlation and scenario configuration

### 3. Run the Simulation and Anchor on Core Results

Move first to the most defensible outputs:

- IRR distribution
- P5 / P50 / P95
- NPV
- Cash-on-Cash
- Equity Multiple

Frame these as the current validated core decision outputs.

### 4. Show Risk and Lender-Style Views

Move to covenant and risk surfaces:

- DSCR
- Debt Yield
- LTV
- related covenant status cards

If a card is using a proxy or placeholder, say so plainly and point to the validation-state caption rather than skipping the section.

### 5. Show Preserved Sensitivity Strength

Use Heatmap 1 and the model-derived Tornado as visual strengths of the demo.

Suggested wording:

- The sensitivity views remain visible because they matter to the workflow.
- Tornado is now a bounded model-derived view; Heatmap 1 is a directional scenario surface.
- Both should be read together with the current validation notes in the UI.

### 6. Show Trace / Explain and Exports

End with the preserved Trace / Explain section and the exports area:

- explainability surface
- workflow completeness
- CSV / JSON / ZIP export path

Use this to position the project as something a future team could later evolve into a broader reporting or business-workflow product.

## Verbal Guardrails

Say:

- “validated core dashboard”
- “preserved advanced workflow surfaces”
- “future candidate for assistant-driven reporting and broader business-system workflows”

Do not say:

- “fully validated across every advanced metric”
- “already integrated into ERP”
- “already has an MCP server”

## Screenshot Priorities

If capturing screenshots for the package, prioritize:

1. top controls plus active-parameter framing
2. IRR distribution and headline return metrics
3. Risk & Covenant Analysis
4. model-derived Tornado and at least one heatmap
5. Trace / Explain and Exports
