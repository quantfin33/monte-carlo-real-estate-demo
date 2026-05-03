"""
Audit tests: smoke run and API schema/deprecation behavior.

Scope:
- A) Smoke & Runability: one run with Base inputs; primary metrics finite
- B) API Contract / Schema: nested metrics present and flat aliases warn

These tests are additive and do not refactor features.
"""

from __future__ import annotations

import math
import warnings

import numpy as np

import rmc_model
import ui_metrics


class TestAuditSmokeRun:
    def test_model_smoke_base(self):
        """Run model once with default params; primary outputs finite."""
        res = rmc_model.run_model(rmc_model.default_params())

        for key in ["IRR", "NPV", "CoC", "EquityMultiple"]:
            assert key in res, f"Missing primary metric: {key}"
            assert np.isfinite(res[key]), f"Primary metric {key} not finite: {res[key]}"


class TestAuditApiContract:
    def test_nested_schema_and_alias_warnings(self):
        """Validate nested schema presence and alias deprecation warnings."""
        df = rmc_model.run_simulation(n=200, seed=42, params=rmc_model.default_params(), parallel=True)

        # Return/value metrics should be nested with coc/npv/equity_multiple/profitability_index
        rv = ui_metrics.return_value_metrics(df)
        for parent in ["coc", "equity_multiple", "npv", "profitability_index"]:
            assert parent in rv, f"Missing nested key: {parent}"
            for child in ["mean", "p5", "p50", "p95"]:
                assert child in rv[parent], f"Missing percentile key: {parent}.{child}"
                # order check only when not NaN
        for parent in ["coc", "equity_multiple", "npv", "profitability_index"]:
            stats = rv[parent]
            if not any(math.isnan(stats[k]) for k in ("p5", "p50", "p95")):
                assert stats["p5"] <= stats["p50"] <= stats["p95"], f"Percentiles out of order for {parent}"

        # Flat alias access should work and emit a DeprecationWarning (first access)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            alias_val = rv["coc_mean"]  # alias for rv['coc']['mean']
            warned_now = any(issubclass(warn.category, DeprecationWarning) for warn in w)
            # If no warning fired now, it may have already been emitted earlier in the suite.
            if not warned_now:
                assert getattr(ui_metrics, "_backward_compat_warning_emitted", False) is True, (
                    "Deprecation warning should be emitted at least once during the run"
                )
            # In all cases the alias must return the nested value
            assert math.isclose(alias_val, rv["coc"]["mean"]) or (
                math.isnan(alias_val) and math.isnan(rv["coc"]["mean"])  # both NaN
            )

        # Risk/ops metrics nested presence tests (ordering)
        ro = ui_metrics.risk_ops_metrics(df)
        for parent in ["yoc", "cap_rate", "ltv", "dscr", "breakeven_occ", "debt_yield_y1"]:
            assert parent in ro, f"Missing nested key: {parent}"
            for child in ["mean", "p5", "p50", "p95"]:
                assert child in ro[parent], f"Missing percentile key: {parent}.{child}"
        for parent in ["yoc", "cap_rate", "ltv", "dscr", "breakeven_occ", "debt_yield_y1"]:
            stats = ro[parent]
            if not any(math.isnan(stats[k]) for k in ("p5", "p50", "p95")):
                assert stats["p5"] <= stats["p50"] <= stats["p95"], f"Percentiles out of order for {parent}"
