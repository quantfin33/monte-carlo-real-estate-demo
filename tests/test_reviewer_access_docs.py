from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STREAMLIT_URL = "https://monte-carlo-real-estate-demo-y4cunxqpckm9ynbgvfffgz.streamlit.app"


def test_readme_has_verified_streamlit_visual_demo_link():
    readme = README.read_text(encoding="utf-8")

    assert STREAMLIT_URL in readme
    assert "<final-streamlit-subdomain>" not in readme
    assert "monte-carlo-real-estate-demo.streamlit.app" not in readme
    assert "visual portfolio review only" in readme


def test_readme_hosted_demo_boundaries_are_explicit():
    readme = README.read_text(encoding="utf-8")
    lowered = readme.lower()

    assert "not production deployment" in lowered
    assert "not investment advice" in lowered
    assert "not live erp/odoo/mcp/sap integration" in lowered
    assert ("production" + "-ready") not in lowered
    assert "production ready" not in lowered
