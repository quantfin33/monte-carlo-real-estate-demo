# Company Demo Handoff

## What This Project Demonstrates

This repository is a business analytics workflow demo built with Python, Streamlit, FastAPI, SQLite, and Docker. Real-estate Monte Carlo scenario analysis is the domain example; the stronger signal is how assumptions move through a dashboard, schema-validated evidence bundle, SQLite run registry, local API layer, containerized review path, and automated test coverage.

The project is suitable for company review as a portfolio example of workflow packaging, backend/API boundaries, reviewer documentation, QA discipline, and ERP-adjacent handoff thinking.

## Why It Matters For Software / Digital Transformation Review

- **Custom software workflow:** input capture, model execution, dashboard output, validation artifacts, and reviewer handoff are organized as one inspectable flow.
- **API/backend capability:** the evidence-bundle workflow is exposed through a local FastAPI wrapper with controlled paths and SQLite run tracking.
- **QA/testing discipline:** docs truth, public claim boundaries, UI/control coverage, evidence-bundle contracts, registry behavior, API behavior, container docs, smoke checks, and broad model tests are covered.
- **Client handoff readiness:** README, launch notes, safe-claim docs, container notes, and structured artifacts give reviewers multiple inspection paths.
- **Business-system awareness:** the package includes a local Odoo/ERP-style dry-run handoff payload as a future mapping pattern for workflow discovery.

## What Is Verified Now

Current verification evidence covers the main reviewer workflow:

- hosted Streamlit visual demo link is available from `README.md`
- local Streamlit launch path is documented in `README_UI_LAUNCH.md`
- core model and engine output contract tests pass
- broad pytest suite passes in the current public package
- rigorous UI/control and public workflow tests are included
- Financial Metric Sensitivity Contract v1 is covered by targeted tests
- schema-validated evidence bundle generation is covered
- optional SQLite run registry behavior is covered
- local FastAPI evidence-bundle wrapper is covered
- local Docker/container run is documented and verified
- screenshots and demo walkthrough media are included for visual review

## Technical Proof Chain

The review path is:

```text
Streamlit dashboard
-> schema-validated evidence bundle
-> SQLite run registry
-> local FastAPI wrapper
-> local Docker/container proof
-> automated tests and safe-claim checks
```

The workflow also includes a local Odoo/ERP-style dry-run handoff payload that demonstrates how reporting data can be shaped for future ERP discovery. External ERP/Odoo connectivity would require a company-specific implementation against real models, permissions, workflows, and deployment constraints.

## Local Review Commands

Run the dashboard locally:

```bash
source .venv/bin/activate
python run_ui.py
```

Run the smoke check:

```bash
source .venv/bin/activate
python run_tests.py smoke
```

Generate a local evidence bundle:

```bash
python scripts/generate_demo_bundle.py --preset base --seed 123 --out /tmp/rmc_demo_bundle --n 2 --sims-per-case 1
```

Start the local API wrapper:

```bash
uvicorn api_app:app --reload
```

Run the local container path:

```bash
docker build -t rmc-evidence-api .
docker run --rm -p 8000:8000 rmc-evidence-api
```

## Current Scope And Future Extensions

The current repo is a portfolio-review workflow and local technical proof. A managed release would require security review, authentication, deployment operations, monitoring, data governance, and client-specific runbooks.

ERP/Odoo appears as a local dry-run payload and mapping pattern. Connecting to a real ERP environment would depend on actual company data models, permissions, business rules, and deployment process.

The analytics outputs support workflow demonstration and model inspection. Financial advisory use, production underwriting reliance, and commercial platform parity are outside the current implementation scope.

Future implementation paths could include a company-specific ERP/Odoo module, hosted backend deployment, authentication, richer role-based workflows, and release operations after separate scoping.

## Safe Company-Facing Summary

This is a public business analytics workflow demo that uses real-estate scenario modeling to demonstrate custom software delivery: dashboard UI, evidence bundles, audit registry, local API, container reproducibility, automated tests, and bounded ERP-adjacent handoff artifacts.
