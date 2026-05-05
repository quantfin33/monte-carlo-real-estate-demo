from __future__ import annotations

import ast
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "UI.py"

STREAMLIT_WIDGETS = {
    "button",
    "checkbox",
    "chat_input",
    "download_button",
    "expander",
    "form_submit_button",
    "multiselect",
    "number_input",
    "radio",
    "selectbox",
    "slider",
    "tabs",
    "text_area",
    "text_input",
}

PROJECT_WIDGET_HELPERS = {"_pct_input"}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == "st":
            return node.attr
    if isinstance(node, ast.Name) and node.id in PROJECT_WIDGET_HELPERS:
        return node.id
    return None


def _label_from_call(node: ast.Call) -> str:
    for keyword in node.keywords:
        if keyword.arg == "label":
            return _label_from_node(keyword.value)
    if node.args:
        return _label_from_node(node.args[0])
    return "<no static label>"


def _label_from_node(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    try:
        return ast.unparse(node)
    except Exception:
        return "<dynamic label>"


def collect_controls(ui_path: Path = UI_PATH) -> list[dict[str, object]]:
    tree = ast.parse(ui_path.read_text(encoding="utf-8"))
    controls: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in STREAMLIT_WIDGETS or name in PROJECT_WIDGET_HELPERS:
            widget_type = "number_input" if name == "_pct_input" else str(name)
            controls.append(
                {
                    "line": int(getattr(node, "lineno", 0)),
                    "type": widget_type,
                    "label": _label_from_call(node),
                    "helper": name == "_pct_input",
                }
            )
    return sorted(controls, key=lambda item: int(item["line"]))


def main() -> int:
    controls = collect_controls()
    counts = Counter(str(control["type"]) for control in controls)
    labels_by_type: dict[str, list[dict[str, object]]] = defaultdict(list)
    for control in controls:
        labels_by_type[str(control["type"])].append(control)

    print(f"UI control inventory for {UI_PATH}")
    print(f"total_controls={len(controls)}")
    print("counts:")
    for widget_type, count in sorted(counts.items()):
        print(f"  {widget_type}: {count}")

    print("controls:")
    for widget_type in sorted(labels_by_type):
        print(f"\n[{widget_type}]")
        for control in labels_by_type[widget_type]:
            helper = " helper=_pct_input" if control["helper"] else ""
            print(f"  line {control['line']}: {control['label']}{helper}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
