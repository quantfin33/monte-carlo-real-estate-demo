#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = ROOT / "artifacts" / "odoo_handoff_demo" / "sample_odoo_handoff_payload.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from odoo_handoff_mapper import build_odoo_dry_run_actions, write_odoo_dry_run_actions  # noqa: E402


def _load_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a local dry-run Odoo handoff action plan without network calls."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to a local Odoo handoff payload JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the dry-run action plan JSON.",
    )
    args = parser.parse_args(argv)

    payload = _load_payload(args.input)
    if args.output is not None:
        output_path = write_odoo_dry_run_actions(args.output, payload)
        print(f"Wrote {output_path.relative_to(ROOT) if output_path.is_relative_to(ROOT) else output_path}")
        return 0

    action_plan = build_odoo_dry_run_actions(payload)
    print(json.dumps(action_plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
