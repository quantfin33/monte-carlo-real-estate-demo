#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import monte_carlo_model  # type: ignore
from demo_presets import load_preset, load_preset_params
from export_contracts import (
    NON_CLAIMS,
    build_ai_context_export,
    build_business_summary_export,
    build_odoo_handoff_payload,
    source_metadata,
    utc_now_iso,
    validate_export_contract,
    write_json,
)
from risk_flags import generate_risk_flags
from run_registry import RunRegistryError, record_bundle_run
from scenario_matrix import build_27_case_matrix, build_scenario_matrix_export, matrix_to_dataframe
from scenario_memo import render_scenario_review_memo


SimulationRunner = Callable[[dict[str, Any], int, int], pd.DataFrame]


def generate_bundle(
    *,
    preset: str,
    seed: int,
    out_dir: Path,
    n: int = 100,
    sims_per_case: int = 10,
    simulation_runner: SimulationRunner | None = None,
    matrix_runner: SimulationRunner | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    preset_payload = load_preset(preset)
    params = load_preset_params(preset)
    runner = simulation_runner or _default_runner

    df = runner(params, int(n), int(seed))
    risk_flags = generate_risk_flags(df, evidence_source="business_summary_export")
    matrix = build_27_case_matrix(
        base_params=params,
        seed=int(seed),
        sims_per_case=int(sims_per_case),
        runner=matrix_runner,
    )

    business_summary = build_business_summary_export(
        df,
        params=params,
        seed=int(seed),
        preset=preset_payload["name"],
        risk_flags=risk_flags,
    )
    ai_context = build_ai_context_export(business_summary)
    odoo_payload = build_odoo_handoff_payload(business_summary)
    scenario_export = build_scenario_matrix_export(
        matrix,
        seed=int(seed),
        inputs=params,
        sims_per_case=int(sims_per_case),
        preset=preset_payload["name"],
    )
    risk_payload = {
        "contract_name": "risk_flags",
        "contract_version": "1.0",
        "source": source_metadata("risk_flags"),
        "generated_at_utc": business_summary["generated_at_utc"],
        "seed": int(seed),
        "preset": preset_payload["name"],
        "flags": risk_flags,
        "non_claims": NON_CLAIMS,
        "network_calls_made": False,
    }

    validation_report = _validate_contracts(
        {
            "business_summary": business_summary,
            "ai_context": ai_context,
            "odoo_handoff_payload": odoo_payload,
            "scenario_matrix": scenario_export,
            "risk_flags": risk_payload,
        }
    )
    validation_report["seed"] = int(seed)
    validation_report["preset"] = preset_payload["name"]

    generated_files: list[str] = []
    generated_files.extend(
        _write_payloads(
            out_dir,
            {
                "inputs.json": {
                    "source": source_metadata("inputs"),
                    "generated_at_utc": business_summary["generated_at_utc"],
                    "preset": preset_payload,
                    "seed": int(seed),
                    "simulation_count": int(n),
                    "sims_per_case": int(sims_per_case),
                    "params": params,
                    "network_calls_made": False,
                },
                "business_summary.json": business_summary,
                "ai_context.json": ai_context,
                "odoo_handoff_payload.json": odoo_payload,
                "scenario_matrix.json": scenario_export,
                "risk_flags.json": risk_payload,
                "validation_report.json": validation_report,
            },
        )
    )

    matrix_csv = out_dir / "scenario_matrix.csv"
    matrix_to_dataframe(matrix).to_csv(matrix_csv, index=False)
    generated_files.append(matrix_csv.name)

    manifest = _build_manifest(
        preset=preset_payload["name"],
        seed=int(seed),
        out_dir=out_dir,
        generated_files=generated_files,
    )

    memo = render_scenario_review_memo(
        business_summary=business_summary,
        scenario_matrix=matrix,
        risk_flags=risk_flags,
        manifest=manifest,
    )
    memo_path = out_dir / "scenario_review_memo.md"
    memo_path.write_text(memo, encoding="utf-8")
    generated_files.append(memo_path.name)

    manifest["generated_files"] = sorted(generated_files)
    write_json(out_dir / "manifest.json", manifest)

    return {
        "bundle_dir": str(out_dir),
        "manifest": manifest,
        "validation_report": validation_report,
        "generated_files": sorted(generated_files + ["manifest.json"]),
    }


def _default_runner(params: dict[str, Any], n: int, seed: int) -> pd.DataFrame:
    return monte_carlo_model.run_simulation(n=n, seed=seed, params=params, parallel=False)


def _validate_contracts(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for contract_name, payload in payloads.items():
        validate_export_contract(contract_name, payload)
        checks.append({"contract": contract_name, "status": "valid"})
    return {
        "source": source_metadata("validation_report"),
        "generated_at_utc": utc_now_iso(),
        "all_valid": True,
        "checks": checks,
        "network_calls_made": False,
    }


def _write_payloads(out_dir: Path, payloads: dict[str, dict[str, Any]]) -> list[str]:
    written: list[str] = []
    for filename, payload in payloads.items():
        write_json(out_dir / filename, payload)
        written.append(filename)
    return written


def _build_manifest(*, preset: str, seed: int, out_dir: Path, generated_files: list[str]) -> dict[str, Any]:
    return {
        "bundle_id": f"{preset}-{seed}",
        "source": source_metadata("manifest"),
        "generated_at_utc": utc_now_iso(),
        "preset": preset,
        "seed": seed,
        "repo_commit": _repo_commit(),
        "output_dir": str(out_dir),
        "generated_files": sorted(generated_files),
        "screenshots": _screenshot_inventory(),
        "tests_run": [
            {
                "command": "not run by bundle generator",
                "status": "not_run",
                "note": "Run pytest separately for verification evidence.",
            }
        ],
        "known_non_claims": NON_CLAIMS,
        "network_calls_made": False,
    }


def _repo_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _screenshot_inventory() -> list[str]:
    screenshot_dir = ROOT / "screenshots"
    if not screenshot_dir.exists():
        return []
    return sorted(str(path.relative_to(ROOT)) for path in screenshot_dir.glob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local portfolio-demo evidence bundle.")
    parser.add_argument("--preset", required=True, help="Demo preset name, e.g. base or downside")
    parser.add_argument("--seed", required=True, type=int, help="Deterministic base seed")
    parser.add_argument("--out", required=True, help="Output directory for the evidence bundle")
    parser.add_argument("--n", type=int, default=100, help="Simulation count for headline metrics")
    parser.add_argument("--sims-per-case", type=int, default=10, help="Simulation count for each matrix case")
    parser.add_argument(
        "--registry-db",
        help="Optional local SQLite path for recording successful demo bundle runs",
    )
    args = parser.parse_args()

    result = generate_bundle(
        preset=args.preset,
        seed=args.seed,
        out_dir=Path(args.out),
        n=args.n,
        sims_per_case=args.sims_per_case,
    )
    if args.registry_db:
        try:
            result["registry"] = record_bundle_run(Path(args.registry_db), result)
        except RunRegistryError as exc:
            print(f"Registry write failed: {exc}", file=sys.stderr)
            return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
