#!/usr/bin/env python3
"""Dry-run and explicitly gated read-only Odoo sandbox probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from odoo_config import OdooConfigError, OdooConnectorConfig, OdooSafetyError
from odoo_connector_contract import OdooJson2Request, ensure_write_allowed
from odoo_json2_client import OdooJson2Client, build_json2_request_preview
from odoo_model_discovery import build_fields_get_request


def main() -> int:
    args = _parse_args()
    if args.dry_run or not args.read_only and not args.allow_sandbox_write:
        return _run_dry_run(args)
    if args.read_only:
        return _run_read_only(args)
    if args.allow_sandbox_write:
        return _run_write_guard_preview(args)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or run explicitly gated Odoo sandbox probes."
    )
    parser.add_argument("--dry-run", action="store_true", help="print request preview only")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="run a read-only sandbox metadata probe when env vars are present",
    )
    parser.add_argument("--model", default="project.task", help="target model to inspect")
    parser.add_argument(
        "--allow-sandbox-write",
        action="store_true",
        help="check write guards; this phase does not create records",
    )
    return parser.parse_args()


def _run_dry_run(args: argparse.Namespace) -> int:
    request = build_fields_get_request(args.model)
    preview = build_json2_request_preview(
        base_url="",
        database=None,
        api_key=None,
        request=request,
    )
    preview["mode"] = "dry_run"
    preview["live_integration"] = False
    preview["connector_implemented"] = True
    preview["external_api_used"] = False
    preview["note"] = (
        "This is a redacted request-shape preview only. No Odoo call was made."
    )
    print(json.dumps(preview, indent=2, sort_keys=True))
    return 0


def _run_read_only(args: argparse.Namespace) -> int:
    try:
        config = OdooConnectorConfig.from_env()
        config.require_database()
    except (OdooConfigError, OdooSafetyError) as exc:
        print(f"Read-only sandbox probe skipped: {exc}")
        return 0

    print("Read-only sandbox probe config:")
    print(json.dumps(config.redacted_dict(), indent=2, sort_keys=True))

    client = OdooJson2Client(config)
    request = build_fields_get_request(args.model)
    response = client.call(
        request.model,
        request.method,
        params=request.params,
        ids=request.ids,
        context=request.context,
    )
    print(json.dumps({"status_code": response.status_code, "ok": response.ok}, indent=2))
    return 0


def _run_write_guard_preview(args: argparse.Namespace) -> int:
    try:
        config = OdooConnectorConfig.from_env()
        config.require_database()
        ensure_write_allowed(config, target_metadata={"verified": True, "model": args.model})
    except (OdooConfigError, OdooSafetyError) as exc:
        print(f"Sandbox write probe skipped: {exc}")
        return 0

    print(
        "Sandbox write guards passed, but this script does not create Odoo records "
        "in this implementation phase."
    )
    print(json.dumps(config.redacted_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
