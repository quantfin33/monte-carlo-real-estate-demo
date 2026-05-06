from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "COMPANY_DEMO_HANDOFF.md",
    ROOT / "README_UI_LAUNCH.md",
    ROOT / "docs" / "SAFE_CLAIMS.md",
    ROOT / "docs" / "WORKFLOW_PRODUCT_ROADMAP.md",
]


def _public_doc_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_DOCS)


def test_public_package_truth_files_exist() -> None:
    expected_paths = [
        *PUBLIC_DOCS,
        ROOT / "scripts" / "generate_demo_bundle.py",
        ROOT / "run_registry.py",
        ROOT / "schemas" / "export_contracts" / "business_summary.schema.json",
        ROOT / "schemas" / "export_contracts" / "odoo_handoff_payload.schema.json",
        ROOT / "schemas" / "export_contracts" / "scenario_matrix.schema.json",
        ROOT / "schemas" / "export_contracts" / "risk_flags.schema.json",
        ROOT / "schemas" / "export_contracts" / "ai_context.schema.json",
    ]
    for path in expected_paths:
        assert path.exists(), f"Missing public package file: {path.relative_to(ROOT)}"


def test_public_docs_describe_current_bundle_and_registry_workflow() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "WORKFLOW_PRODUCT_ROADMAP.md").read_text(encoding="utf-8")

    assert "python scripts/generate_demo_bundle.py --preset base --seed 123" in readme
    assert "--registry-db /tmp/rmc_demo_registry.sqlite" in readme
    assert "scripts/generate_demo_bundle.py" in readme
    assert "run_registry.py" in readme
    assert "schemas/export_contracts/" in readme
    assert "docs/WORKFLOW_PRODUCT_ROADMAP.md" in readme
    assert "docs/SAFE_CLAIMS.md" in roadmap
    assert "network_calls_made=false" in roadmap
    assert "sidecar-only" in readme


def test_public_docs_do_not_reference_stale_internal_files() -> None:
    text = _public_doc_text()
    forbidden = [
        "KEEWAYS",
        "Keeways",
        "MONTE_CARLO_PROJECT_DOSSIER.md",
        "scripts/logic_probe.py",
        "logic_probe",
        "root `monte_carlo_model.py` file is missing",
        "current root snapshot is missing `monte_carlo_model.py`",
        "does not currently have `streamlit`, `altair`, or `pytest`",
        "Fresh local execution could not be confirmed",
        "**Recommendation: Not ready",
        "venv lacks pytest",
        "venv lacks Streamlit",
        "venv lacks Altair",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_docs_keep_claims_bounded() -> None:
    combined = "\n".join(
        [
            _public_doc_text(),
            (ROOT / "docs" / "POSITIONING_MEMO.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8"),
        ]
    ).lower()
    forbidden_claims = [
        "odoo integration is implemented",
        "erp integration is implemented",
        "mcp server is implemented",
        "has full production validation",
        "fully production validated",
        "is production ready",
        "is " + "production" + "-ready",
        "production" + "-ready without qualification",
        "production" + "-ready odoo integration is complete",
        "live erp connector" " already working",
        "live odoo connector" " already working",
        "live erp integration is implemented",
        "live odoo integration is implemented",
        "sap integration is implemented",
        "provides investment advice",
        "offers investment advice",
        "investment" + " recommendation engine is implemented",
        "investment" + " recommendations are included",
        "strong" + "_buy",
        "buy" + "/sell verdict",
        "argus" + "/dealpath replacement",
        "replacement for argus or dealpath",
    ]
    for phrase in forbidden_claims:
        assert phrase not in combined


def test_public_docs_have_no_private_paths_or_stale_sample_values() -> None:
    text = _public_doc_text()
    forbidden = [
        "/" + "Users/chris",
        "Desktop/" + "BACKUPS",
        "286" + "3451",
        "2,863" + ",451",
        "500" + "5220",
        "5,005" + ",220",
        "$3." + "67M",
        "$5." + "0M",
    ]
    for phrase in forbidden:
        assert phrase not in text
