#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from odoo_handoff_payload import write_odoo_handoff_payload  # noqa: E402


def main() -> int:
    output_path = write_odoo_handoff_payload()
    print(f"Wrote {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
