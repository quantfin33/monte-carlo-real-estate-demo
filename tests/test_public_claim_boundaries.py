from __future__ import annotations

import re
from pathlib import Path

from tests.ui_app_helpers import all_visible_text, run_app_once


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEXT_PATHS = [
    "README.md",
    "COMPANY_DEMO_HANDOFF.md",
    "README_UI_LAUNCH.md",
    ".env.example",
    "docs/AI_ERP_EXTENSION_ROADMAP.md",
    "docs/DEMO_ASSUMPTION_BOUNDARY.md",
    "docs/LOCAL_CONTAINER_RUN.md",
    "docs/ODOO_CONNECTOR_BUILD_PLAN.md",
    "docs/ODOO_INTEGRATION_RESEARCH.md",
    "docs/SAFE_CLAIMS.md",
    "docs/WORKFLOW_PRODUCT_ROADMAP.md",
    "UI.py",
    "api_app.py",
]

PRIVATE_OR_SECRET_REGEXES = [
    "/" + "Users/chris",
    "Desktop/" + "BACKUPS",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"OPENAI_API_KEY\s*=\s*sk-[A-Za-z0-9_-]{20,}",
    r"GITHUB_TOKEN\s*=\s*(ghp|github_pat)_[A-Za-z0-9_]{20,}",
    r"AWS_SECRET_ACCESS_KEY\s*=\s*[A-Za-z0-9/+=]{20,}",
]

STALE_VALUE_PATTERNS = [
    "2863451",
    "2,863,451",
    "5005220",
    "5,005,220",
    "$3.67M",
    "$5.0M",
]

UNSAFE_CLAIM_PATTERNS = [
    "production-ready",
    "hosted production deployment",
    "live ERP connector",
    "live Odoo integration",
    "live MCP integration",
    "live SAP integration",
    "investment recommendation",
    "STRONG_BUY",
    "BUY/SELL verdict",
    "ARGUS/Dealpath replacement",
    "guaranteed investment performance",
]

SAFE_BOUNDARY_CONTEXT = [
    "do not claim",
    "explicit non-claims",
    "abort if",
    "future only",
    "not ",
    "no ",
    "never ",
    "without ",
    "outside the claim boundary",
    "claim boundary",
    "roadmap-only",
    "not included",
    "does not include",
    "not be described",
    "must stay qualified",
    "before sandbox evidence exists",
]


def _read_public_texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for relative in PUBLIC_TEXT_PATHS:
        path = ROOT / relative
        assert path.exists(), f"Public claim-boundary path is missing: {relative}"
        texts[relative] = path.read_text(encoding="utf-8")
    return texts


def _context(text: str, start: int, window: int = 220) -> str:
    return text[max(0, start - window) : start + window]


def _claim_mentions(text: str, phrase: str) -> list[str]:
    mentions: list[str] = []
    for match in re.finditer(re.escape(phrase), text, flags=re.IGNORECASE):
        context = _context(text, match.start()).lower()
        if not any(cue in context for cue in SAFE_BOUNDARY_CONTEXT):
            mentions.append(_context(text, match.start(), window=120))
    return mentions


def test_public_text_files_do_not_include_private_paths_secrets_or_stale_values():
    texts = _read_public_texts()
    failures: list[str] = []
    for relative, text in texts.items():
        for pattern in PRIVATE_OR_SECRET_REGEXES:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"{relative}: {pattern}")
        for pattern in STALE_VALUE_PATTERNS:
            if pattern.lower() in text.lower():
                failures.append(f"{relative}: {pattern}")

    assert not failures, "Unexpected private/secret/stale public text: " + "; ".join(failures)


def test_public_text_files_allow_only_explicit_safe_boundary_claim_mentions():
    texts = _read_public_texts()
    failures: list[str] = []
    for relative, text in texts.items():
        for phrase in UNSAFE_CLAIM_PATTERNS:
            for mention in _claim_mentions(text, phrase):
                failures.append(f"{relative}: {phrase!r} in {mention!r}")

    assert not failures, "Unsafe public claim wording found: " + "; ".join(failures)


def test_default_app_visible_text_respects_public_claim_boundary():
    app = run_app_once()
    visible_text = all_visible_text(app)

    for pattern in PRIVATE_OR_SECRET_REGEXES:
        assert re.search(pattern, visible_text, flags=re.IGNORECASE) is None
    for pattern in STALE_VALUE_PATTERNS:
        assert pattern.lower() not in visible_text.lower()

    failures: list[str] = []
    for phrase in UNSAFE_CLAIM_PATTERNS:
        failures.extend(_claim_mentions(visible_text, phrase))

    assert not failures, "Unsafe visible app claim wording found: " + "; ".join(failures)
