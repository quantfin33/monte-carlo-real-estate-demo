from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dossier_blocks_stale_repo_truth_claims() -> None:
    text = (ROOT / "MONTE_CARLO_PROJECT_DOSSIER.md").read_text(encoding="utf-8")
    forbidden = [
        "root `rmc_model.py` file is missing",
        "current root snapshot is missing `rmc_model.py`",
        "does not currently have `streamlit`, `altair`, or `pytest`",
        "Fresh local execution could not be confirmed",
        "**Recommendation: Not ready",
        "venv lacks pytest",
        "venv lacks Streamlit",
        "venv lacks Altair",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_keeways_docs_keep_claims_bounded() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "docs" / "KEEWAYS_SAFE_CLAIMS.md",
            ROOT / "docs" / "KEEWAYS_POSITIONING_MEMO.md",
            ROOT / "docs" / "KEEWAYS_DEMO_SCRIPT.md",
        ]
    ).lower()
    forbidden_claims = [
        "odoo integration is implemented",
        "erp integration is implemented",
        "mcp server is implemented",
        "has full production validation",
        "fully production validated",
        "is production ready",
        "production-ready without qualification",
    ]
    for phrase in forbidden_claims:
        assert phrase not in combined
