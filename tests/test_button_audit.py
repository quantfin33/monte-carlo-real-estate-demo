from __future__ import annotations

import math

import pandas as pd

from button_audit import (
    compare_metric,
    recompute_heatmap_metrics,
    recompute_main_metrics,
    recompute_tornado_metrics,
    record_button_run,
)


def _sample_result_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "IRR": [0.10, 0.15, 0.20, 0.25],
            "NPV": [-1_000_000.0, 0.0, 1_000_000.0, 2_000_000.0],
            "CoC": [0.06, 0.08, 0.10, 0.12],
            "EquityMultiple": [1.2, 1.4, 1.6, 1.8],
            "Equity": [10_000_000.0, 10_000_000.0, 10_000_000.0, 10_000_000.0],
            "DSCR": [1.10, 1.30, 1.40, 1.50],
            "DebtYield_Y1": [0.08, 0.09, 0.10, 0.11],
            "YieldOnCost": [0.07, 0.08, 0.09, 0.10],
            "CapRate": [0.075, 0.080, 0.085, 0.090],
            "LTV": [0.55, 0.60, 0.65, 0.70],
            "BreakEvenOcc": [0.70, 0.75, 0.80, 0.85],
            "PhysicalOccupancyRate": [0.82, 0.83, 0.84, 0.85],
            "EconomicOccupancyRate": [0.80, 0.81, 0.82, 0.83],
            "Prepay_Cost_Sale": [0.0, 5_000.0, 10_000.0, 0.0],
            "PrepayAtSale_Toggle": [True, True, False, True],
        }
    )


def test_run_monte_carlo_audit_writes_button_and_metric_rows(tmp_path) -> None:
    df = _sample_result_df()
    metrics = recompute_main_metrics(df)

    summary = record_button_run(
        "Run Monte Carlo Simulation",
        {"seed": 123, "sims": len(df)},
        df,
        {"Row Count": len(df)},
        metrics,
        tmp_path,
    )

    assert summary["status"] == "PASS"
    assert summary["row_count"] == len(df)
    button_runs = pd.read_csv(tmp_path / "button_runs.csv")
    tieouts = pd.read_csv(tmp_path / "metric_tieouts.csv")
    assert len(button_runs) == 1
    assert len(tieouts) >= 20
    assert "IRR P50" in set(tieouts["metric"])
    assert (tmp_path / "latest_run_monte_carlo_simulation_raw.csv").exists()


def test_percent_scaling_catches_decimal_vs_percent_mistake() -> None:
    row = compare_metric(
        displayed=15.0,
        recomputed=0.15,
        tolerance=0.005,
        scale="percent_points",
        metric="IRR P50",
        formula="p50(IRR) * 100",
        severity_if_fail="P1",
    )

    assert row["pass"] is False
    assert row["severity"] == "P1"
    assert math.isclose(float(row["delta"]), 14.85, rel_tol=0, abs_tol=1e-12)


def test_irr_percentiles_recompute_from_raw_result() -> None:
    df = _sample_result_df()
    tieouts = {row["metric"]: row for row in recompute_main_metrics(df)}

    assert math.isclose(tieouts["IRR P5"]["recomputed_value"], 10.75, abs_tol=1e-12)
    assert math.isclose(tieouts["IRR P50"]["recomputed_value"], 17.5, abs_tol=1e-12)
    assert math.isclose(tieouts["IRR P95"]["recomputed_value"], 24.25, abs_tol=1e-12)


def test_npv_coc_equity_multiple_and_pi_are_independently_recomputed() -> None:
    df = _sample_result_df()
    tieouts = {row["metric"]: row for row in recompute_main_metrics(df)}

    assert math.isclose(tieouts["NPV P50"]["recomputed_value"], 500_000.0, abs_tol=1e-12)
    assert math.isclose(tieouts["Cash-on-Cash P50"]["recomputed_value"], 9.0, abs_tol=1e-12)
    assert math.isclose(tieouts["Equity Multiple P50"]["recomputed_value"], 1.5, abs_tol=1e-12)
    assert math.isclose(tieouts["PI P50"]["recomputed_value"], 1.05, abs_tol=1e-12)


def test_heatmap_min_max_range_and_top_cell_tie_out() -> None:
    df = pd.DataFrame(
        {
            "ExitCap": ["8.0%", "8.0%", "9.0%"],
            "RentGrowth": ["2.0%", "3.0%", "2.0%"],
            "IRR_pct": [11.0, 14.5, 9.25],
        }
    )
    tieouts = {row["metric"]: row for row in recompute_heatmap_metrics(df)}

    assert math.isclose(tieouts["Heatmap Min IRR"]["recomputed_value"], 9.25)
    assert math.isclose(tieouts["Heatmap Max IRR"]["recomputed_value"], 14.5)
    assert math.isclose(tieouts["Heatmap Range"]["recomputed_value"], 5.25)
    assert math.isclose(tieouts["Heatmap Top Cell IRR"]["recomputed_value"], 14.5)


def test_tornado_deltas_equal_shocked_metric_minus_base_metric() -> None:
    df = pd.DataFrame(
        {
            "parameter": ["Interest Rate"],
            "low_case": ["5.75%"],
            "high_case": ["7.75%"],
            "base_metric": [0.15],
            "low_metric": [0.17],
            "high_metric": [0.13],
            "low_delta": [0.02],
            "high_delta": [-0.02],
            "abs_impact": [0.02],
            "status": ["model-derived"],
        }
    )
    tieouts = recompute_tornado_metrics(df)

    assert all(row["pass"] for row in tieouts)
    assert "Tornado Interest Rate Low Delta" in {row["metric"] for row in tieouts}


def test_audit_append_preserves_prior_runs_and_unique_run_ids(tmp_path) -> None:
    df = _sample_result_df()
    metrics = recompute_main_metrics(df)
    first = record_button_run("Run Monte Carlo Simulation", {"seed": 1}, df, {}, metrics, tmp_path)
    second = record_button_run("Run Monte Carlo Simulation", {"seed": 2}, df, {}, metrics, tmp_path)

    button_runs = pd.read_csv(tmp_path / "button_runs.csv")
    assert len(button_runs) == 2
    assert first["run_id"] != second["run_id"]
    assert set(button_runs["run_id"]) == {first["run_id"], second["run_id"]}


def test_mismatch_above_tolerance_sets_fail_and_severity(tmp_path) -> None:
    df = _sample_result_df()
    bad_row = compare_metric(
        10.0,
        12.0,
        tolerance=0.005,
        scale="percent_points",
        metric="IRR P50",
        formula="p50(IRR) * 100",
        severity_if_fail="P1",
    )
    summary = record_button_run("Run Monte Carlo Simulation", {"seed": 999}, df, {}, [bad_row], tmp_path)

    tieouts = pd.read_csv(tmp_path / "metric_tieouts.csv")
    assert summary["status"] == "FAIL"
    assert summary["p1_count"] == 1
    assert str(tieouts.loc[0, "pass"]).lower() == "false"
    assert tieouts.loc[0, "severity"] == "P1"
