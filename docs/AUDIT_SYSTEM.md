# Audit System

This repo uses tiered audit gates so future changes can be checked consistently without turning every change into a full-suite run.

## Audit Tiers

| Tier | Purpose | Blocking Level |
| --- | --- | --- |
| 0 | Git state, public/local mismatch, dirty files | Blocks staging if unexpected |
| 1 | Secrets, private paths, cache files, generated database files | Blocks public sharing |
| 2 | Docs truth, reviewer access docs, container docs, claim boundaries | Blocks public sharing |
| 3 | Streamlit UI/control/AppTest coverage | Blocks UI/control changes |
| 4 | FastAPI, evidence bundle, SQLite registry contracts | Blocks API/workflow changes |
| 5 | Financial metric contract tests | Blocks financial/model changes |
| 6 | Docker/local container proof | Blocks container packaging changes |
| 7 | Broad pytest diagnostic | Blocks broad-suite health claims |
| 8 | Dependency and supply-chain audit | Blocks dependency/security claims |

## Tier Commands

Tier 0:

```bash
git status --short
git log --oneline -8
git log origin/main --oneline -8
git diff --name-only
```

Tier 1:

```bash
git grep -n -I -E '/(Users)/(chris)|Desktop/(BACKUPS)|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|password\s*=|secrets[.]toml' -- . || true
find . -maxdepth 2 -type f \( -name '*.[s]qlite' -o -name '*.[d]b' -o -name '.[e]nv' -o -name 'secrets[.]toml' -o -name '*.[p]yc' -o -name '.[D]S_Store' \) -print | sort
```

Tier 2:

```bash
python scripts/audit_gates.py quick
python -m pytest tests/test_public_claim_boundaries.py -q -o addopts=''
```

Tier 3:

```bash
python scripts/audit_gates.py ui
```

Tier 4:

```bash
python scripts/audit_gates.py public
```

Tier 5:

```bash
python scripts/audit_gates.py financial
```

Tier 6:

```bash
python scripts/audit_gates.py docker
```

Tier 7:

```bash
python -m pytest -q -o addopts=''
```

Tier 8:

```bash
python scripts/audit_gates.py supply-chain
```

## Reporting Standard

Every lock-readiness audit should report:

- files changed
- protected-file check
- commands run
- pass/fail results
- public claim scan result
- dependency/security notes when relevant
- whether public GitHub and local clone match
- final judgment: `READY TO LOCK`, `READY AFTER SMALL FIXES`, or `NOT READY TO LOCK`

## Sharing Rules

- Public-facing claims must stay aligned with `docs/SAFE_CLAIMS.md`.
- A passing broad suite does not create production-readiness, investment-advice, live ERP/Odoo/MCP/SAP, or platform-replacement claims.
- Generated screenshots, media, artifacts, SQLite files, and local caches should not be changed unless the layer explicitly approves them.
