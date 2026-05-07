from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_container_packaging_files_exist() -> None:
    expected = [
        ROOT / "Dockerfile",
        ROOT / ".dockerignore",
        ROOT / ".env.example",
        ROOT / "docs" / "LOCAL_CONTAINER_RUN.md",
    ]
    for path in expected:
        assert path.exists(), f"Missing container packaging file: {path.relative_to(ROOT)}"


def test_readme_links_to_local_container_docs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/LOCAL_CONTAINER_RUN.md" in readme
    assert "local container proof only" in readme
    assert "not hosted deployment" in readme
    assert "not live ERP/Odoo/MCP/SAP integration" in readme
    assert "not investment advice" in readme


def test_container_docs_keep_public_claim_boundary() -> None:
    text = (ROOT / "docs" / "LOCAL_CONTAINER_RUN.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "local reproducibility" in lowered
    assert "not production deployment" in lowered
    assert "not cloud hosting" in lowered
    assert "not investment advice" in lowered
    assert "not live erp/odoo/mcp/sap integration" in lowered
    assert "docker build -t rmc-evidence-api ." in text
    assert "docker run --rm -p 8000:8000 rmc-evidence-api" in text
    assert "curl http://127.0.0.1:8000/health" in text


def test_dockerignore_blocks_local_and_secret_material() -> None:
    entries = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    required = {
        ".git",
        ".venv",
        "__pycache__/",
        "*.pyc",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".DS_Store",
        ".env",
        ".streamlit/secrets.toml",
        "*.sqlite",
        "*.db",
        "logs/",
        "*.log",
        "rmc_api_bundles/",
        "container_output/",
        "docker_output/",
    }
    missing = required - entries
    assert not missing, f".dockerignore missing expected entries: {sorted(missing)}"


def test_env_example_contains_only_safe_local_values() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "RMC_API_BUNDLE_ROOT=/tmp/rmc_api_bundles" in text
    assert "RMC_API_REGISTRY_DB=/tmp/rmc_api_bundles/demo_bundle_runs.sqlite" in text
    assert "Do not commit real secrets" in text
    assert "OPENAI_API_KEY=" not in text
