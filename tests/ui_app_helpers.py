from __future__ import annotations

from pathlib import Path
from typing import Iterable

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "UI.py"

UNSAFE_VISIBLE_PHRASES = [
    "/" + "Users/chris",
    "Desktop/" + "BACKUPS",
    "production-ready",
    "live ERP connector already working",
    "live Odoo integration",
    "investment recommendation",
    "STRONG_BUY",
    "BUY/SELL verdict",
    "ARGUS/Dealpath replacement",
]

SAFE_BOUNDARY_PHRASES = [
    "not production-ready",
    "not production ready",
    "not investment advice",
    "not an investment recommendation",
    "not live odoo integration",
    "not live erp integration",
    "not live erp/odoo integration",
    "not an argus/dealpath replacement",
]


def run_app_once(timeout: int = 60) -> AppTest:
    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=timeout)
    assert not app.exception
    return app


def rerun_app(app: AppTest, timeout: int = 60) -> AppTest:
    app.run(timeout=timeout)
    assert not app.exception
    return app


def labels(elements: Iterable[object]) -> list[str]:
    return [str(getattr(element, "label", "")) for element in elements]


def values(elements: Iterable[object]) -> list[str]:
    visible: list[str] = []
    for element in elements:
        for attr in ("value", "body", "label", "placeholder"):
            value = getattr(element, attr, None)
            if value:
                visible.append(str(value))
                break
    return visible


def all_visible_text(app: AppTest) -> str:
    text: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "info",
        "warning",
        "success",
        "metric",
        "chat_message",
    ):
        text.extend(values(getattr(app, attr, [])))
    text.extend(labels(app.number_input))
    text.extend(labels(app.selectbox))
    text.extend(labels(app.checkbox))
    text.extend(labels(app.slider))
    text.extend(labels(app.button))
    text.extend(labels(app.expander))
    return "\n".join(text)


def element_by_label(elements: Iterable[object], label: str):
    matches = [element for element in elements if getattr(element, "label", None) == label]
    assert matches, f"Could not find Streamlit widget labeled {label!r}"
    return matches[0]


def assert_no_unsafe_visible_phrases(text: str) -> None:
    lower_text = text.lower()
    for safe_phrase in SAFE_BOUNDARY_PHRASES:
        lower_text = lower_text.replace(safe_phrase, "")
    failures = [
        phrase
        for phrase in UNSAFE_VISIBLE_PHRASES
        if phrase.lower() in lower_text
    ]
    assert not failures, f"Unsafe visible phrases found: {failures}"
