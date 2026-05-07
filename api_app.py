from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from run_registry import RunRegistryError, fetch_bundle_run, record_bundle_run
from scripts.generate_demo_bundle import generate_bundle


DEFAULT_BUNDLE_ROOT = Path("/tmp/rmc_api_bundles")
DEFAULT_REGISTRY_FILENAME = "demo_bundle_runs.sqlite"
EXPECTED_JSON_ARTIFACTS = {
    "manifest": "manifest.json",
    "validation_report": "validation_report.json",
    "risk_flags": "risk_flags.json",
}
MEMO_FILENAME = "scenario_review_memo.md"


app = FastAPI(
    title="RMC Evidence Bundle API",
    description=(
        "Local portfolio-demo API for generating and reading schema-validated "
        "evidence bundles. It is not hosted deployment, investment advice, or "
        "live ERP/Odoo/MCP/SAP integration."
    ),
    version="1.3.0",
)


class RunBundleRequest(BaseModel):
    preset: str = Field(..., min_length=1, max_length=64)
    seed: int = Field(..., ge=0, le=2_147_483_647)
    n: int = Field(default=100, ge=1, le=5_000)
    sims_per_case: int = Field(default=10, ge=1, le=100)

    class Config:
        extra = "forbid"


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "rmc-evidence-api",
        "network_calls_made": False,
    }


@app.post("/run-bundle")
def run_bundle(request: RunBundleRequest) -> dict[str, Any]:
    _validate_preset_name(request.preset)
    out_dir = _new_bundle_dir(request.preset, request.seed)
    registry_db = _registry_db_path()

    try:
        result = generate_bundle(
            preset=request.preset,
            seed=request.seed,
            out_dir=out_dir,
            n=request.n,
            sims_per_case=request.sims_per_case,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _assert_local_validated_result(result)

    try:
        registry = record_bundle_run(registry_db, result)
    except RunRegistryError as exc:
        raise HTTPException(status_code=500, detail=f"Registry write failed: {exc}") from exc

    run_id = registry["run_id"]
    validation_report = result["validation_report"]
    return {
        "run_id": run_id,
        "preset": result["manifest"]["preset"],
        "seed": result["manifest"]["seed"],
        "validation_report": {
            "all_valid": validation_report["all_valid"],
            "network_calls_made": validation_report["network_calls_made"],
        },
        "validation_report_all_valid": validation_report["all_valid"],
        "network_calls_made": False,
        "generated_files": result["generated_files"],
        "artifact_endpoints": _artifact_endpoints(run_id),
    }


@app.get("/bundle/{run_id}")
def get_bundle(run_id: str) -> dict[str, Any]:
    row, bundle_dir = _registered_bundle(run_id)
    manifest = _read_json(bundle_dir, EXPECTED_JSON_ARTIFACTS["manifest"])
    validation_report = _read_json(bundle_dir, EXPECTED_JSON_ARTIFACTS["validation_report"])
    return {
        "run_id": run_id,
        "registry": _public_registry_row(row),
        "manifest": manifest,
        "validation_report": validation_report,
        "network_calls_made": False,
        "artifact_endpoints": _artifact_endpoints(run_id),
    }


@app.get("/risk-flags/{run_id}")
def get_risk_flags(run_id: str) -> dict[str, Any]:
    _, bundle_dir = _registered_bundle(run_id)
    return _read_json(bundle_dir, EXPECTED_JSON_ARTIFACTS["risk_flags"])


@app.get("/memo/{run_id}", response_class=PlainTextResponse)
def get_memo(run_id: str) -> PlainTextResponse:
    _, bundle_dir = _registered_bundle(run_id)
    path = _expected_artifact_path(bundle_dir, MEMO_FILENAME)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Memo artifact not found.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


def _bundle_root() -> Path:
    return Path(os.environ.get("RMC_API_BUNDLE_ROOT", str(DEFAULT_BUNDLE_ROOT))).expanduser()


def _registry_db_path() -> Path:
    default_path = _bundle_root() / DEFAULT_REGISTRY_FILENAME
    return Path(os.environ.get("RMC_API_REGISTRY_DB", str(default_path))).expanduser()


def _new_bundle_dir(preset: str, seed: int) -> Path:
    root = _bundle_root()
    safe_preset = _safe_slug(preset)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    out_dir = root / f"{safe_preset}-{seed}-{timestamp}-{suffix}"
    return _ensure_under_root(out_dir, root)


def _registered_bundle(run_id: str) -> tuple[dict[str, Any], Path]:
    row = fetch_bundle_run(_registry_db_path(), run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown run_id.")
    output_dir = row.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        raise HTTPException(status_code=404, detail="Bundle output directory not available.")
    bundle_dir = _ensure_under_root(Path(output_dir), _bundle_root())
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        raise HTTPException(status_code=404, detail="Bundle directory not found.")
    return row, bundle_dir


def _read_json(bundle_dir: Path, filename: str) -> dict[str, Any]:
    path = _expected_artifact_path(bundle_dir, filename)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact {filename} not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_artifact_path(bundle_dir: Path, filename: str) -> Path:
    allowed = set(EXPECTED_JSON_ARTIFACTS.values()) | {MEMO_FILENAME}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Artifact is not exposed by this API.")
    return _ensure_under_root(bundle_dir / filename, bundle_dir)


def _ensure_under_root(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and not resolved_path.is_relative_to(resolved_root):
        raise HTTPException(status_code=404, detail="Bundle path is outside the configured API root.")
    return resolved_path


def _validate_preset_name(preset: str) -> None:
    if not preset or any(not (char.isalnum() or char in ("-", "_")) for char in preset):
        raise HTTPException(status_code=400, detail="Preset may only contain letters, numbers, '-' or '_'.")


def _safe_slug(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in value)
    return cleaned.strip("-_") or "preset"


def _assert_local_validated_result(result: dict[str, Any]) -> None:
    manifest = result.get("manifest")
    validation_report = result.get("validation_report")
    if not isinstance(manifest, dict) or not isinstance(validation_report, dict):
        raise HTTPException(status_code=500, detail="Bundle result is missing validation metadata.")
    if validation_report.get("all_valid") is not True:
        raise HTTPException(status_code=500, detail="Bundle validation did not pass.")
    if validation_report.get("network_calls_made") is not False or manifest.get("network_calls_made") is not False:
        raise HTTPException(status_code=500, detail="Bundle result reported network calls.")


def _artifact_endpoints(run_id: str) -> dict[str, str]:
    return {
        "bundle": f"/bundle/{run_id}",
        "risk_flags": f"/risk-flags/{run_id}",
        "memo": f"/memo/{run_id}",
    }


def _public_registry_row(row: dict[str, Any]) -> dict[str, Any]:
    public_row = dict(row)
    files_json = public_row.get("generated_files_json")
    if isinstance(files_json, str):
        public_row["generated_files"] = json.loads(files_json)
    public_row.pop("generated_files_json", None)
    return public_row
