from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUN_REGISTRY_TABLE = "demo_bundle_runs"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
  run_id TEXT PRIMARY KEY,
  preset TEXT NOT NULL,
  seed INTEGER NOT NULL,
  generated_at_utc TEXT NOT NULL,
  output_dir TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK (validation_status IN ('valid')),
  validation_report_path TEXT NOT NULL,
  generated_files_json TEXT NOT NULL,
  repo_commit TEXT NOT NULL,
  network_calls_made INTEGER NOT NULL CHECK (network_calls_made = 0),
  created_at_utc TEXT NOT NULL
);
""".format(table_name=RUN_REGISTRY_TABLE)


class RunRegistryError(RuntimeError):
    """Raised when a bundle run cannot be recorded in the local registry."""


def record_bundle_run(db_path: Path | str, bundle_result: dict[str, Any]) -> dict[str, Any]:
    """Record a successful local evidence-bundle run in an optional SQLite registry."""
    record = _build_record(bundle_result)
    resolved_db_path = Path(db_path).expanduser()
    if resolved_db_path.parent != Path(""):
        resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(resolved_db_path) as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.execute(
                f"""
                INSERT INTO {RUN_REGISTRY_TABLE} (
                  run_id,
                  preset,
                  seed,
                  generated_at_utc,
                  output_dir,
                  validation_status,
                  validation_report_path,
                  generated_files_json,
                  repo_commit,
                  network_calls_made,
                  created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["run_id"],
                    record["preset"],
                    record["seed"],
                    record["generated_at_utc"],
                    record["output_dir"],
                    record["validation_status"],
                    record["validation_report_path"],
                    record["generated_files_json"],
                    record["repo_commit"],
                    record["network_calls_made"],
                    record["created_at_utc"],
                ),
            )
    except sqlite3.Error as exc:
        raise RunRegistryError(f"Could not record bundle run in SQLite registry: {exc}") from exc

    return {
        "enabled": True,
        "db_path": str(resolved_db_path),
        "run_id": record["run_id"],
    }


def _build_record(bundle_result: dict[str, Any]) -> dict[str, Any]:
    manifest = _require_dict(bundle_result, "manifest")
    validation_report = _require_dict(bundle_result, "validation_report")
    generated_files = bundle_result.get("generated_files")

    if validation_report.get("all_valid") is not True:
        raise RunRegistryError("Registry writes require validation_report.all_valid=true.")
    if validation_report.get("network_calls_made") is not False:
        raise RunRegistryError("Registry writes require validation_report.network_calls_made=false.")
    if manifest.get("network_calls_made") is not False:
        raise RunRegistryError("Registry writes require manifest.network_calls_made=false.")
    if not isinstance(generated_files, list) or not all(
        isinstance(filename, str) for filename in generated_files
    ):
        raise RunRegistryError("Registry writes require bundle_result.generated_files as a list of strings.")

    preset = _require_str(manifest, "preset")
    seed = _require_int(manifest, "seed")
    generated_at_utc = _require_str(manifest, "generated_at_utc")
    output_dir = _require_str(manifest, "output_dir")
    repo_commit = _require_str(manifest, "repo_commit")
    created_at_utc = _utc_now_iso()
    run_id = _run_id(preset=preset, seed=seed, created_at_utc=created_at_utc)

    return {
        "run_id": run_id,
        "preset": preset,
        "seed": seed,
        "generated_at_utc": generated_at_utc,
        "output_dir": output_dir,
        "validation_status": "valid",
        "validation_report_path": str(Path(output_dir) / "validation_report.json"),
        "generated_files_json": json.dumps(sorted(generated_files), sort_keys=True),
        "repo_commit": repo_commit,
        "network_calls_made": 0,
        "created_at_utc": created_at_utc,
    }


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RunRegistryError(f"Registry writes require bundle_result.{key}.")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RunRegistryError(f"Registry writes require non-empty {key}.")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RunRegistryError(f"Registry writes require integer {key}.")
    return value


def _run_id(*, preset: str, seed: int, created_at_utc: str) -> str:
    compact_time = created_at_utc.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    safe_preset = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in preset)
    return f"{safe_preset}-{seed}-{compact_time}-{uuid.uuid4().hex[:8]}"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
