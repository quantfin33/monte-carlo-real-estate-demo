from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.filterwarnings("ignore")


def test_streamlit_initial_render_has_no_exceptions() -> None:
    app_test = pytest.importorskip("streamlit.testing.v1")
    app = app_test.AppTest.from_file(str(Path(__file__).resolve().parents[1] / "UI.py"))
    app.run(timeout=60)

    assert not app.exception

    button_labels = [button.label for button in app.button]
    assert any("Run Monte Carlo Simulation" in label for label in button_labels)
    assert "Build Model-Derived Tornado" in button_labels
