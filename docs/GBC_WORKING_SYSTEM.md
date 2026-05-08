# Grounded Build Cycle Working System

This project uses a Grounded Build Cycle (GBC) for future changes. The goal is to keep portfolio presentation, financial logic, UI behavior, artifacts, and public claims controlled while still making steady improvements.

## Required Cycle

1. **Repo truth check**
   - Run `git status --short`, inspect recent commits, and identify dirty files before planning.
   - Confirm whether local files differ from public `origin/main`.

2. **Scope lock**
   - State the goal, allowed files, protected files, commands to run, and stop conditions.
   - Keep each change narrow enough to review and revert.

3. **Protected-file list**
   - Treat `UI.py`, `monte_carlo_model.py`, screenshots, artifacts, API/Docker behavior, public media, and GitHub metadata as protected unless the task explicitly approves them.
   - Treat financial model behavior as protected unless a focused financial-contract layer approves it.

4. **Focused implementation**
   - Edit only the approved files.
   - Avoid feature creep, broad refactors, generated artifact churn, and unrelated cleanup.

5. **Focused tests**
   - Run the tests closest to the changed behavior first.
   - Use `-o addopts=''` for focused pytest commands when the repo-level report settings are unnecessary.

6. **Public/claim scan**
   - Scan changed public-facing files for private paths, secrets, stale values, and unsafe claims.
   - Keep ERP/Odoo, deployment, investment, and platform-parity wording bounded.

7. **Broad diagnostic**
   - Run broad pytest only after focused gates pass or when a change could affect shared contracts.
   - Classify failures before fixing anything outside the locked scope.

8. **Lock-readiness report**
   - Report changed files, tests run, pass/fail status, scan result, protected-file check, and remaining risks.
   - State whether the layer is ready to stage and commit.

9. **Stage, commit, and push only after approval**
   - Stage only approved files.
   - Verify staged file list before commit.
   - Push only after the user explicitly asks for it.

## Stop Conditions

Stop and report before continuing if:

- a protected file needs editing outside the approved scope
- `UI.py` or `monte_carlo_model.py` would need unexpected changes
- financial logic would change without an approved financial-contract layer
- screenshots, media, or artifacts would need regeneration
- README/public presentation files would need editing in a non-presentation task
- unexpected dirty files appear
- focused public gates fail
- generated artifact drift appears
- default test runtime becomes too slow for normal review
- the task expands beyond the locked goal

## Default Command Profiles

Use `scripts/audit_gates.py` for repeatable local checks:

```bash
python scripts/audit_gates.py quick
python scripts/audit_gates.py public
python scripts/audit_gates.py financial
python scripts/audit_gates.py ui
python scripts/audit_gates.py full
python scripts/audit_gates.py supply-chain
python scripts/audit_gates.py docker
```

The quick and public profiles are the normal reviewer-safe gates. The full, UI, and Docker profiles are heavier and should be used when the change touches those surfaces.
