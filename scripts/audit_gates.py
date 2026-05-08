#!/usr/bin/env python3
"""Run repeatable local audit gate profiles for the public demo repo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass


PYTEST_BASE = [sys.executable, "-m", "pytest"]


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    required: bool = True


@dataclass
class Result:
    name: str
    command: tuple[str, ...]
    status: str
    duration: float
    returncode: int


def _pytest(*paths: str) -> tuple[str, ...]:
    return (*PYTEST_BASE, *paths, "-q", "-o", "addopts=")


PROFILES: dict[str, tuple[Gate, ...]] = {
    "quick": (
        Gate(
            "docs/reviewer/container docs",
            _pytest(
                "tests/test_docs_truth.py",
                "tests/test_reviewer_access_docs.py",
                "tests/test_container_docs.py",
            ),
        ),
        Gate("smoke", (sys.executable, "run_tests.py", "smoke")),
    ),
    "public": (
        Gate(
            "docs/reviewer/container docs",
            _pytest(
                "tests/test_docs_truth.py",
                "tests/test_reviewer_access_docs.py",
                "tests/test_container_docs.py",
            ),
        ),
        Gate(
            "api/registry/demo/public workflow",
            _pytest(
                "tests/test_api_app.py",
                "tests/test_run_registry.py",
                "tests/test_demo_adaptation_workflow.py",
                "tests/test_public_workflow_contract.py",
            ),
        ),
        Gate("public claim boundaries", _pytest("tests/test_public_claim_boundaries.py")),
        Gate("smoke", (sys.executable, "run_tests.py", "smoke")),
    ),
    "financial": (
        Gate(
            "financial metric contracts",
            _pytest(
                "tests/audit/test_financial_metric_sensitivity_contract_v1.py",
                "tests/test_dscr_wiring.py",
                "tests/test_debt_yield_sensitivity.py",
                "tests/test_coc_sensitivity.py",
            ),
        ),
    ),
    "ui": (
        Gate(
            "ui/control contracts",
            _pytest(
                "tests/test_ui_control_contract.py",
                "tests/test_ui_default_visible_contract.py",
                "tests/test_ui_branch_activation.py",
                "tests/test_ui_numeric_boundaries.py",
                "tests/test_ui_option_matrix.py",
                "tests/test_ui_command_surfaces.py",
            ),
        ),
    ),
    "full": (
        Gate(
            "public gates",
            _pytest(
                "tests/test_docs_truth.py",
                "tests/test_reviewer_access_docs.py",
                "tests/test_container_docs.py",
                "tests/test_api_app.py",
                "tests/test_run_registry.py",
                "tests/test_demo_adaptation_workflow.py",
                "tests/test_public_workflow_contract.py",
                "tests/test_public_claim_boundaries.py",
            ),
        ),
        Gate(
            "financial metric contracts",
            _pytest(
                "tests/audit/test_financial_metric_sensitivity_contract_v1.py",
                "tests/test_dscr_wiring.py",
                "tests/test_debt_yield_sensitivity.py",
                "tests/test_coc_sensitivity.py",
            ),
        ),
        Gate(
            "ui/control contracts",
            _pytest(
                "tests/test_ui_control_contract.py",
                "tests/test_ui_default_visible_contract.py",
                "tests/test_ui_branch_activation.py",
                "tests/test_ui_numeric_boundaries.py",
                "tests/test_ui_option_matrix.py",
                "tests/test_ui_command_surfaces.py",
            ),
        ),
        Gate("broad pytest", (*PYTEST_BASE, "-q", "-o", "addopts=")),
        Gate("smoke", (sys.executable, "run_tests.py", "smoke")),
    ),
    "supply-chain": (
        Gate("pip check", (sys.executable, "-m", "pip", "check")),
    ),
}


def run_gate(gate: Gate) -> Result:
    print(f"\n==> {gate.name}")
    print("$ " + " ".join(gate.command))
    started = time.monotonic()
    completed = subprocess.run(gate.command, text=True)
    duration = time.monotonic() - started
    status = "PASS" if completed.returncode == 0 else ("SKIP" if not gate.required else "FAIL")
    print(f"{status}: {gate.name} ({duration:.2f}s)")
    return Result(gate.name, gate.command, status, duration, completed.returncode)


def run_supply_chain() -> list[Result]:
    results = [run_gate(gate) for gate in PROFILES["supply-chain"]]
    if shutil.which("pip-audit") is None:
        print("\nSKIP: pip-audit is not installed.")
        print("Install with: python -m pip install -r requirements_audit.txt")
        results.append(Result("pip-audit", ("pip-audit", "-r", "requirements.txt"), "SKIP", 0.0, 0))
        return results

    results.append(run_gate(Gate("pip-audit", ("pip-audit", "-r", "requirements.txt"))))
    return results


def run_docker() -> list[Result]:
    commands = [
        Gate(
            "remove prior audit container",
            ("docker", "rm", "-f", "rmc-evidence-api-audit"),
            required=False,
        ),
        Gate("docker build", ("docker", "build", "-t", "rmc-evidence-api-audit", ".")),
        Gate(
            "docker run",
            (
                "docker",
                "run",
                "--rm",
                "-d",
                "-p",
                "8000:8000",
                "--name",
                "rmc-evidence-api-audit",
                "rmc-evidence-api-audit",
            ),
        ),
    ]
    results: list[Result] = []
    try:
        for gate in commands:
            result = run_gate(gate)
            results.append(result)
            if result.returncode != 0 and gate.required:
                return results

        results.append(_wait_for_health())
        return results
    finally:
        stop = subprocess.run(("docker", "stop", "rmc-evidence-api-audit"), text=True)
        status = "PASS" if stop.returncode == 0 else "SKIP"
        results.append(Result("docker stop", ("docker", "stop", "rmc-evidence-api-audit"), status, 0.0, 0))


def _wait_for_health() -> Result:
    command = ("curl", "-fsS", "http://127.0.0.1:8000/health")
    started = time.monotonic()
    last_returncode = 1
    for _ in range(20):
        completed = subprocess.run(command, text=True)
        if completed.returncode == 0:
            duration = time.monotonic() - started
            print(f"\nPASS: docker health ({duration:.2f}s)")
            return Result("docker health", command, "PASS", duration, 0)
        last_returncode = completed.returncode
        time.sleep(1)
    duration = time.monotonic() - started
    print(f"\nFAIL: docker health ({duration:.2f}s)")
    return Result("docker health", command, "FAIL", duration, last_returncode)


def run_profile(profile: str) -> list[Result]:
    if profile == "supply-chain":
        return run_supply_chain()
    if profile == "docker":
        if shutil.which("docker") is None:
            print("SKIP: Docker is not installed.")
            return [Result("docker", ("docker", "--version"), "SKIP", 0.0, 0)]
        return run_docker()

    return [run_gate(gate) for gate in PROFILES[profile]]


def summarize(results: Sequence[Result]) -> int:
    print("\n=== Audit Gate Summary ===")
    failed = False
    for result in results:
        print(f"{result.status:>4} {result.duration:>7.2f}s  {result.name}")
        if result.status == "FAIL":
            failed = True
    if failed:
        print("\nNext action: inspect the first failing gate before broadening scope.")
        return 1
    print("\nNext action: profile passed; continue with the next GBC layer or lock-readiness audit.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=sorted([*PROFILES.keys(), "docker"]),
        help="Audit profile to run.",
    )
    args = parser.parse_args()
    return summarize(run_profile(args.profile))


if __name__ == "__main__":
    raise SystemExit(main())
