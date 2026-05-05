from __future__ import annotations

import streamlit as st
st.set_page_config(page_title="Monte Carlo Model — Enhanced", layout="wide")

import copy
import io
import json
import sys
import zipfile
from pathlib import Path

import altair as alt
import time
import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

try:
    import monte_carlo_model
    import scenario_randomizer
    import ui_metrics  # Pure metric calculation functions
    from button_audit import (
        record_button_run,
        recompute_heatmap_metrics,
        recompute_main_metrics,
        recompute_tornado_metrics,
    )
    from tornado_sensitivity import build_tornado_sensitivity_data
except Exception as e:
    st.title("Monte Carlo Model (Minimal)")
    st.error(f"Couldn't import monte_carlo_model.py, scenario_randomizer.py, ui_metrics.py, or audit helpers from: {THIS_DIR}\n\n{e}")
    st.stop()

try:
    import trace_tools
except Exception:
    trace_tools = None

try:
    import ai_context
    import ai_analyst
except Exception:
    ai_context = None
    ai_analyst = None

# --- Lightweight app logger (structure/debug only) ---
def _app_log(msg: str):
    try:
        logdir = THIS_DIR / 'artifacts'
        logdir.mkdir(parents=True, exist_ok=True)
        with (logdir / 'app_debug.log').open('a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            f.flush()
    except Exception:
        pass


def _render_ai_analyst_chat_section() -> None:
    st.header("AI Analyst")
    st.caption("Ask the dashboard to explain the latest simulation results, risks, sensitivity views, and trace outputs.")
    answer_style_options = ["Short", "Detailed", "Client summary"]
    current_answer_style = st.session_state.get("ai_answer_style", "Short")
    if current_answer_style not in answer_style_options:
        current_answer_style = "Short"
    answer_style = st.selectbox(
        "Answer style",
        answer_style_options,
        index=answer_style_options.index(current_answer_style),
        key="ai_answer_style",
    )

    analyst_df = st.session_state.get("df")
    if analyst_df is None or analyst_df.empty:
        st.info("Run a simulation first to activate AI analysis.")
        return

    if ai_context is None or ai_analyst is None:
        st.warning("AI analyst helpers are unavailable in this runtime. The rest of the dashboard is unaffected.")
        return

    if not ai_analyst.has_live_openai_configured():
        st.info("Demo analyst mode is active. Add `OPENAI_API_KEY` to enable live AI responses.")

    try:
        context = ai_context.build_ai_context(
            analyst_df,
            trace_payload=st.session_state.get("trace_payload"),
            selected_scenario=st.session_state.get("scenario"),
            heatmap_1=st.session_state.get("df_hm"),
            heatmap_2=st.session_state.get("hm2_df"),
            tornado=st.session_state.get("tornado_df"),
        )
    except Exception as exc:
        st.warning(f"AI analysis context could not be built from the current results: {exc}")
        return

    fingerprint_payload = {
        "scenario": context.get("scenario", {}).get("name"),
        "row_count": context.get("simulation", {}).get("row_count"),
        "irr_p50": context.get("core_metrics", {}).get("irr", {}).get("p50"),
        "npv_p50": context.get("core_metrics", {}).get("npv", {}).get("p50"),
        "answer_style": answer_style,
        "trace_available": context.get("trace", {}).get("available"),
    }
    context_fingerprint = json.dumps(fingerprint_payload, sort_keys=True, default=str)
    if st.session_state.get("ai_context_fingerprint") != context_fingerprint:
        st.session_state["ai_context_fingerprint"] = context_fingerprint
        st.session_state["ai_chat_messages"] = []

    for message in st.session_state.get("ai_chat_messages", []):
        with st.chat_message(message.get("role", "assistant")):
            st.markdown(message.get("content", ""))

    quick_prompts = [
        "Explain these results in simple business terms",
        "What are the main risks?",
        "Why are the returns strong?",
        "What should I review before trusting this scenario?",
    ]
    prompt_cols = st.columns(2)
    selected_prompt = None
    for index, prompt in enumerate(quick_prompts):
        with prompt_cols[index % 2]:
            if st.button(prompt, key=f"ai_quick_prompt_{index}", use_container_width=True):
                selected_prompt = prompt

    typed_question = st.chat_input(
        "Ask about the current simulation results, risks, charts, or trace surface.",
        key="ai_analyst_chat_input",
    )
    question = selected_prompt or typed_question
    if not question:
        return

    st.session_state["ai_chat_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    answer = ai_analyst.answer_question(question, context, answer_style=answer_style)
    st.session_state["ai_chat_messages"].append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)


def _clear_smart_scenario_result_state() -> None:
    for key in ("df", "df_hm", "hm2_df", "tornado_df", "trace_payload"):
        st.session_state[key] = None
    st.session_state["ai_chat_messages"] = []
    st.session_state["ai_context_fingerprint"] = None


def _render_smart_scenario_generator() -> None:
    st.markdown("### Smart Scenario Generator")
    st.caption(
        "Generate a coherent demo/testing assumption set, review what changed, "
        "then manually run the simulation."
    )

    profile_col, seed_col = st.columns([2, 1])
    with profile_col:
        current_profile = st.session_state.get("smart_scenario_profile", "Base Variation")
        if current_profile not in scenario_randomizer.SCENARIO_PROFILES:
            st.session_state.smart_scenario_profile = "Base Variation"
        profile = st.selectbox(
            "Scenario profile",
            scenario_randomizer.SCENARIO_PROFILES,
            key="smart_scenario_profile",
        )
    with seed_col:
        generator_seed = st.number_input(
            "Generator seed",
            min_value=0,
            max_value=999_999_999,
            step=1,
            key="smart_scenario_seed",
        )

    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    with action_col1:
        if st.button("Generate Plausible Scenario", type="primary"):
            try:
                current_inputs = scenario_randomizer.extract_current_inputs(st.session_state)
                st.session_state.smart_scenario_pending = scenario_randomizer.generate_scenario(
                    profile=profile,
                    seed=int(generator_seed),
                    current_inputs=current_inputs,
                )
                st.session_state.smart_scenario_error = None
            except Exception as exc:
                st.session_state.smart_scenario_pending = None
                st.session_state.smart_scenario_error = str(exc)

    pending_scenario = st.session_state.get("smart_scenario_pending")
    with action_col2:
        if st.button("Apply Generated Scenario", disabled=not bool(pending_scenario)):
            if not pending_scenario:
                st.session_state.smart_scenario_error = "Generate a scenario before applying."
            else:
                values = dict(pending_scenario.get("values", {}))
                errors = scenario_randomizer.validate_generated_scenario(values)
                if errors:
                    st.session_state.smart_scenario_error = "; ".join(errors)
                else:
                    for key, value in values.items():
                        st.session_state[key] = value
                    st.session_state.smart_scenario_last_applied = pending_scenario
                    st.session_state.smart_scenario_pending = None
                    st.session_state.smart_scenario_error = None
                    _clear_smart_scenario_result_state()
                    st.rerun()

    with action_col3:
        if st.button("Reset to Base Inputs"):
            for key, value in scenario_randomizer.base_reset_inputs().items():
                st.session_state[key] = value
            st.session_state.smart_scenario_pending = None
            st.session_state.smart_scenario_last_applied = None
            st.session_state.smart_scenario_error = None
            _clear_smart_scenario_result_state()
            st.rerun()

    if st.session_state.get("smart_scenario_error"):
        st.error(f"Smart scenario could not be generated or applied: {st.session_state.smart_scenario_error}")

    pending_scenario = st.session_state.get("smart_scenario_pending")
    if pending_scenario:
        resolved_profile = pending_scenario.get("resolved_profile", pending_scenario.get("profile"))
        st.success(
            f"Pending smart scenario ready: {pending_scenario.get('profile')} "
            f"(seed {pending_scenario.get('seed')}, coherent profile {resolved_profile})."
        )
        changes = pending_scenario.get("changes", [])
        if changes:
            preview_df = pd.DataFrame(changes)[
                ["field", "old_value", "new_value", "direction", "reason"]
            ]
            st.dataframe(preview_df, hide_index=True, use_container_width=True)
        else:
            st.info("Generated scenario matches the current visible inputs.")
        st.caption(pending_scenario.get("caveat", scenario_randomizer.CAVEAT))

    if st.session_state.get("smart_scenario_last_applied"):
        applied = st.session_state.smart_scenario_last_applied
        st.caption(
            f"Last applied smart scenario: {applied.get('profile')} "
            f"with seed {applied.get('seed')}. Click Run Monte Carlo Simulation when ready."
        )


# derive defaults from the engine, with safe fallbacks
try:
    params = monte_carlo_model.default_params()
    _DEFAULT_RENT_PSF = float(params.get("in_place_rent_psf", 23.64))
    _DEFAULT_TOTAL_RSF = float(params.get("total_rsf", 630594))
    _DEFAULT_INITIAL_OCC = float(params.get("initial_occupancy", 0.826))
    _DEFAULT_MARKET_RENT = float(params.get("market_rent_psf", 27.0))
    _DEFAULT_PURCHASE_PRICE = float(params.get("purchase_price", 108000000))
    _DEFAULT_OPEX_START = float(params.get("operating_expenses_start", 2500000))
    _DEFAULT_OPEX_GROWTH = float(params.get("opex_growth_rate", 0.03))
    _DEFAULT_TAX_RATE = float(params.get("property_tax_rate", 0.015))
    _DEFAULT_TAX_MODE = str(params.get("tax_mode", "independent"))
    _DEFAULT_TAX_GROWTH = float(params.get("tax_growth_rate", 0.025))

    # Get tax_reassessment defaults
    tax_reassess = params.get("tax_reassessment", {})
    _DEFAULT_TAX_REASSESS_ON_REFI = bool(tax_reassess.get("on_refi", True))
    _DEFAULT_TAX_REASSESS_ON_SALE = bool(tax_reassess.get("on_sale", True))
    _DEFAULT_TAX_REASSESS_ASSESSMENT_RATIO = float(tax_reassess.get("assessment_ratio", 1.00))
    _DEFAULT_TAX_REASSESS_MAX_INCREASE_CAP_PCT = float(tax_reassess.get("max_increase_cap_pct", 0.1))
except Exception:
    _DEFAULT_RENT_PSF = 23.64
    _DEFAULT_TOTAL_RSF = 630594
    _DEFAULT_INITIAL_OCC = 0.826
    _DEFAULT_MARKET_RENT = 27.0
    _DEFAULT_PURCHASE_PRICE = 108000000
    _DEFAULT_OPEX_START = 2500000
    _DEFAULT_OPEX_GROWTH = 0.03
    _DEFAULT_TAX_RATE = 0.015
    _DEFAULT_TAX_MODE = "independent"
    _DEFAULT_TAX_GROWTH = 0.025

    # Fallback tax_reassessment defaults
    _DEFAULT_TAX_REASSESS_ON_REFI = True
    _DEFAULT_TAX_REASSESS_ON_SALE = True
    _DEFAULT_TAX_REASSESS_ASSESSMENT_RATIO = 1.00
    _DEFAULT_TAX_REASSESS_MAX_INCREASE_CAP_PCT = 0.1

# --- Function Definitions (must come before usage) ---

def _get(metric_block: dict, name: str, stat: str, default=None):
    """Helper to safely extract nested metric values avoiding KeyErrors."""
    try:
        return metric_block.get(name, {}).get(stat, default)
    except Exception:
        return default


def _json_default(o):
    """Sanitize NumPy/Pandas/path-like objects for json.dumps(default=...)."""
    try:
        import numpy as _np
        import pandas as _pd
    except Exception:  # if libs aren't available for any reason
        class _Dummy: pass
        _np = _Dummy(); _np.integer = (); _np.floating = (); _np.bool_ = (); _np.ndarray = ()
        _pd = _Dummy(); _pd.Timestamp = (); _pd.Series = ()
    from pathlib import Path as _Path

    # NumPy scalars & arrays
    if isinstance(o, _np.integer):
        return int(o)
    if isinstance(o, _np.floating):
        return float(o)
    if isinstance(o, _np.bool_):
        return bool(o)
    if isinstance(o, _np.ndarray):
        return o.tolist()

    # Pandas types
    if isinstance(o, _pd.Timestamp):
        return o.isoformat()
    if isinstance(o, _pd.Series):
        return o.tolist()

    # Path-like
    if isinstance(o, _Path):
        return str(o)

    # Safe fallback
    return str(o)


def _audit_input_snapshot(button_name: str) -> dict:
    """Capture the current UI inputs that are useful for replaying a button audit."""
    keys = [
        "scenario",
        "sims",
        "seed",
        "stage2",
        "purchase_price",
        "in_place_rent_psf",
        "total_rsf",
        "initial_occupancy",
        "market_rent_psf",
        "operating_expenses_start",
        "opex_growth_rate",
        "property_tax_rate",
        "tax_mode",
        "tax_growth_rate",
        "debt_ratio",
        "interest_rate",
        "exit_cap_left",
        "exit_cap_mode",
        "exit_cap_right",
        "exit_cap_override",
        "market_rent_growth_min",
        "market_rent_growth_max",
        "prepay",
        "prepay_at_sale",
        "hm_sims",
        "tornado_n_per_case",
        "tornado_metric",
        "tornado_stat",
    ]
    payload = {"button_name": button_name}
    for key in keys:
        if key in st.session_state:
            value = st.session_state.get(key)
            try:
                json.dumps(value, default=_json_default)
                payload[key] = value
            except Exception:
                payload[key] = str(value)
    return payload


def _record_button_audit(
    button_name: str,
    output_df: pd.DataFrame,
    recomputed_metrics: list[dict] | dict,
    summary_metrics: dict | None = None,
) -> dict | None:
    try:
        summary = record_button_run(
            button_name,
            _audit_input_snapshot(button_name),
            output_df,
            summary_metrics or {},
            recomputed_metrics,
            THIS_DIR / "artifacts" / "button_audit",
        )
        st.session_state.latest_button_audit = summary
        st.session_state.latest_button_audit_error = ""
        _app_log(
            f"button_audit:{button_name}:status={summary.get('status')} "
            f"run_id={summary.get('run_id')} failed={summary.get('failed_count')}"
        )
        if summary.get("status") != "PASS":
            st.warning(
                f"Audit tie-out found {summary.get('failed_count', 0)} blocking mismatch(es). "
                "Open Audit Evidence below for CSV details."
            )
        return summary
    except Exception as exc:
        st.session_state.latest_button_audit_error = str(exc)
        _app_log(f"button_audit:{button_name}:error {exc}")
        st.warning(f"Button audit logging failed: {exc}")
        return None


def _main_displayed_metrics_for_audit(df: pd.DataFrame) -> dict[str, float]:
    displayed: dict[str, float] = {"Row Count": float(len(df))}
    try:
        irr = ui_metrics.irr_stats(df)
        displayed.update(
            {
                "IRR MEAN": float(irr["mean"]) * 100.0,
                "IRR MEDIAN": float(irr["median"]) * 100.0,
                "IRR P5": float(irr["p5"]) * 100.0,
                "IRR P50": float(irr["p50"]) * 100.0,
                "IRR P95": float(irr["p95"]) * 100.0,
                "P(IRR >= 15%)": float(irr["prob_ge_15"]) * 100.0,
            }
        )
    except Exception:
        pass

    try:
        rv = ui_metrics.return_value_metrics(df)
        displayed.update(
            {
                "NPV P50": float(_get(rv, "npv", "p50", float("nan"))),
                "Cash-on-Cash P50": float(_get(rv, "coc", "p50", float("nan"))) * 100.0,
                "Equity Multiple P50": float(_get(rv, "equity_multiple", "p50", float("nan"))),
                "PI P50": float(_get(rv, "profitability_index", "p50", float("nan"))),
            }
        )
    except Exception:
        pass

    try:
        min_dscr_series = None
        for cand in ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr"]:
            if cand in df.columns:
                min_dscr_series = pd.to_numeric(df[cand], errors="coerce")
                break
        if min_dscr_series is None and "DSCR" in df.columns:
            min_dscr_series = pd.to_numeric(df["DSCR"], errors="coerce")
        if min_dscr_series is not None:
            displayed["Min DSCR Avg"] = float(min_dscr_series.mean())
            displayed["% Runs < 1.25x"] = float((min_dscr_series < 1.25).mean() * 100.0)

        min_dy_series = None
        for cand in ["MinDY", "MinDebtYield", "DebtYield_Min", "min_dy", "mindebtyield"]:
            if cand in df.columns:
                min_dy_series = pd.to_numeric(df[cand], errors="coerce")
                break
        if min_dy_series is None and "DebtYield_Y1" in df.columns:
            min_dy_series = pd.to_numeric(df["DebtYield_Y1"], errors="coerce")
        if min_dy_series is not None:
            displayed["Min Debt Yield Avg"] = float(min_dy_series.mean() * 100.0)
    except Exception:
        pass

    return displayed


def _heatmap_displayed_metrics_for_audit(df_hm: pd.DataFrame) -> dict[str, float]:
    displayed: dict[str, float] = {"Heatmap Row Count": float(len(df_hm))}
    try:
        irr_pct = pd.to_numeric(df_hm["IRR_pct"], errors="coerce")
        if not irr_pct.isna().all():
            hm_min = float(irr_pct.min())
            hm_max = float(irr_pct.max())
            displayed.update(
                {
                    "Heatmap Min IRR": hm_min,
                    "Heatmap Max IRR": hm_max,
                    "Heatmap Range": hm_max - hm_min,
                    "Heatmap Top Cell IRR": float(df_hm.loc[irr_pct.idxmax(), "IRR_pct"]),
                    "Heatmap Finite IRR Cells": float(irr_pct.dropna().shape[0]),
                }
            )
    except Exception:
        pass
    return displayed


def _is_finite_number(value) -> bool:
    try:
        return value is not None and np.isfinite(float(value))
    except Exception:
        return False


def _value_or_placeholder(value, formatter, placeholder: str = "—") -> str:
    return formatter(value) if _is_finite_number(value) else placeholder


def _range_caption(p5, p95, formatter, unavailable: str = "Not available in current contract") -> str:
    if _is_finite_number(p5) and _is_finite_number(p95):
        return f"P5 {formatter(p5)} • P95 {formatter(p95)}"
    return unavailable


def _triple_caption(p5, p50, p95, formatter, unavailable: str = "Not available in current contract") -> str:
    if _is_finite_number(p5) and _is_finite_number(p50) and _is_finite_number(p95):
        return f"P5 {formatter(p5)} • P50 {formatter(p50)} • P95 {formatter(p95)}"
    return unavailable


def _render_validation_note(level: str, message: str):
    renderer = {
        "info": st.info,
        "warning": st.warning,
        "error": st.error,
        "success": st.success,
    }.get(level, st.info)
    renderer(message)


def _pct_input(
    label: str,
    *,
    value: float,
    min_value: float = 0.0,
    max_value: float = 1.0,
    step: float = 0.01,
    format: str = "%.1f",
    help: str | None = None,
    key: str | None = None,
) -> float:
    """Render a percent-style number_input while storing a decimal in session/model state."""
    pct_value = float(value) * 100.0
    pct_result = st.number_input(
        label,
        min_value=float(min_value) * 100.0,
        max_value=float(max_value) * 100.0,
        value=pct_value,
        step=float(step) * 100.0,
        format=format,
        help=help,
        key=key,
    )
    return float(pct_result) / 100.0


def _demo_sale_month() -> int | None:
    return st.session_state.get("sale_month")


def _demo_heatmap2_grids() -> tuple[list[float], list[float]]:
    rate_center = float(st.session_state.interest_rate)
    ltv_center = float(st.session_state.debt_ratio)
    rate_grid = [
        round(min(max(rate_center + delta, 0.0), 0.20), 4)
        for delta in (-0.02, -0.01, 0.0, 0.01, 0.02)
    ]
    ltv_grid = [
        round(min(max(ltv_center + delta, 0.0), 0.75), 4)
        for delta in (-0.20, -0.10, 0.0, 0.10, 0.20)
    ]
    return rate_grid, ltv_grid

@st.cache_data(ttl=600, show_spinner=False)
def _run_sim_cached(n: int, seed: int, params: dict, parallel: bool = True) -> pd.DataFrame:
    _app_log(f"_run_sim_cached: start n={n} seed={seed}")
    df = monte_carlo_model.run_simulation(n=int(n), seed=int(seed), params=params, parallel=parallel)
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    return df


def _selected_run_row_for_trace(df: pd.DataFrame, run_idx: int) -> pd.Series:
    if "_RunIndex" in df.columns:
        run_idx_series = pd.to_numeric(df["_RunIndex"], errors="coerce")
        matches = df.loc[run_idx_series == int(run_idx)]
        if not matches.empty:
            return matches.iloc[0]
    return df.iloc[int(run_idx)]


def _compact_trace_payload_for_ai(df: pd.DataFrame, params: dict, seed: int) -> dict:
    unavailable = {
        "available": False,
        "summary": "Trace engine support exists, but this chat context does not currently include the selected-run trace bundle.",
    }
    if trace_tools is None:
        return unavailable
    if df is None or df.empty:
        return unavailable

    try:
        run_idx, _median_irr = trace_tools.find_median_run(df)
        selected = _selected_run_row_for_trace(df, int(run_idx))
        expected_irr = float(selected["IRR"])
        bundle = trace_tools.run_trace_simulation(
            params=params,
            base_seed=int(seed),
            run_idx=int(run_idx),
            mode="p50_trace",
            expected_irr=expected_irr,
        )
        if not isinstance(bundle, dict) or "error" in bundle:
            _app_log(f"ai_trace:unavailable {bundle.get('error') if isinstance(bundle, dict) else 'invalid bundle'}")
            return unavailable

        trace_cashflows = bundle.get("trace_cashflows") or {}
        trace_summary = bundle.get("trace_summary") or {}
        consistency = trace_cashflows.get("consistency_check") or {}
        if trace_summary.get("replay_matches_selected") is False:
            _app_log("ai_trace:replay mismatch")
            return unavailable

        cash_flow_series = trace_cashflows.get("cash_flow_series") or []
        return {
            "available": True,
            "summary": "Trace/Explain context is available for the selected run; cash-flow count and IRR recompute status are included.",
            "mode": trace_summary.get("mode"),
            "run_index": trace_summary.get("run_index"),
            "cash_flow_count": trace_summary.get("cash_flow_count") or len(cash_flow_series),
            "engine_irr": trace_cashflows.get("engine_irr") or trace_summary.get("irr"),
            "computed_irr": trace_cashflows.get("computed_irr"),
            "consistency_passed": consistency.get("passed"),
            "replay_matches_selected": trace_summary.get("replay_matches_selected"),
        }
    except Exception as exc:
        _app_log(f"ai_trace:error {exc}")
        return unavailable


def _run_many(n: int, seed: int, use_stage2: bool, scenario: str | None = None) -> pd.DataFrame:
    params = copy.deepcopy(monte_carlo_model.default_params())

    # Apply scenario overrides if available
    if scenario and hasattr(monte_carlo_model, "apply_scenario_overrides"):
        try:
            params = monte_carlo_model.apply_scenario_overrides(params, scenario)
        except Exception:
            pass

    # UI-only overrides (do not edit monte_carlo_model.py)
    params["in_place_rent_psf"] = float(st.session_state.in_place_rent_psf)
    params["total_rsf"] = float(st.session_state.total_rsf)
    params["initial_occupancy"] = float(st.session_state.initial_occupancy)
    params["market_rent_psf"] = float(st.session_state.market_rent_psf)
    params["purchase_price"] = float(st.session_state.purchase_price)
    params["operating_expenses_start"] = float(st.session_state.operating_expenses_start)
    params["opex_growth_rate"] = float(st.session_state.opex_growth_rate)
    params["property_tax_rate"] = float(st.session_state.property_tax_rate)
    params["tax_mode"] = str(st.session_state.tax_mode)
    params["tax_growth_rate"] = float(st.session_state.tax_growth_rate)

    # Set tax_reassessment dictionary
    params["tax_reassessment"] = {
        "on_refi": bool(st.session_state.tax_reassess_on_refi),
        "on_sale": bool(st.session_state.tax_reassess_on_sale),
        "assessment_ratio": float(st.session_state.tax_reassess_assessment_ratio),
        "max_increase_cap_pct": float(st.session_state.tax_reassess_max_increase_cap_pct),
    }

    # Set new parameters
    params["vacancy_auto_lease"] = bool(st.session_state.vacancy_auto_lease)
    params["controllable_opex_pct"] = float(st.session_state.controllable_opex_pct)
    params["default_controllable_cap_pct"] = float(st.session_state.default_controllable_cap_pct)
    params["debt_ratio"] = float(st.session_state.debt_ratio)
    params["interest_rate"] = float(st.session_state.interest_rate)
    params["refi_year"] = int(st.session_state.refi_year)
    params["refi_cost_rate"] = float(st.session_state.refi_cost_rate)
    params["interest_only_years"] = int(st.session_state.interest_only_years)
    params["amort_years"] = int(st.session_state.amort_years)

    # Set additional new parameters
    params["post_refi_io_years"] = int(st.session_state.post_refi_io_years)
    params["discount_rate"] = float(st.session_state.discount_rate)
    params["acq_cost_rate"] = float(st.session_state.acq_cost_rate)
    params["financing_fee_rate"] = float(st.session_state.financing_fee_rate)
    params["rate_cap_cost"] = float(st.session_state.rate_cap_cost)
    params["working_capital_reserve"] = float(st.session_state.working_capital_reserve)
    params["seller_reserve_credit"] = float(st.session_state.seller_reserve_credit)
    params["contingency_reserve"] = float(st.session_state.contingency_reserve)

    # Set transfer tax parameters
    params["transfer_tax_buy_rate"] = float(st.session_state.transfer_tax_buy_rate)
    params["transfer_tax_sell_rate"] = float(st.session_state.transfer_tax_sell_rate)

    # Set working capital true-up parameters
    params["wc_true_up_close_dollar"] = float(st.session_state.wc_true_up_close_dollar)
    params["wc_true_up_close_pct_of_opex"] = float(st.session_state.wc_true_up_close_pct_of_opex)
    params["wc_true_up_sale_dollar"] = float(st.session_state.wc_true_up_sale_dollar)
    params["wc_true_up_sale_pct_of_opex"] = float(st.session_state.wc_true_up_sale_pct_of_opex)

    # Set capex and sale parameters
    params["capex_schedule"] = st.session_state.capex_schedule
    params["sale_cost_rate"] = float(st.session_state.sale_cost_rate)
    params["price_terminal_with_buyer_tax"] = bool(st.session_state.price_terminal_with_buyer_tax)
    params["sale_month"] = _demo_sale_month()

    # Set debt / covenant / refi control parameters
    params["amortization_granularity"] = str(st.session_state.amortization_granularity)
    params["covenant_track"] = bool(st.session_state.covenant_track)
    params["covenant_thresholds"] = st.session_state.covenant_thresholds.copy()
    params["covenant_action"] = str(st.session_state.covenant_action)
    params["refi_boxes"] = st.session_state.refi_boxes.copy()

    # Set prepayment parameters
    params["prepay"] = st.session_state.prepay.copy()
    params["prepay_at_sale"] = bool(st.session_state.prepay_at_sale)
    params["debug_return_schedule"] = bool(st.session_state.debug_return_schedule)

    # Set reserve parameters
    params["reserve_per_rsf"] = float(st.session_state.reserve_per_rsf)
    params["reserve_start_year"] = int(st.session_state.reserve_start_year)
    params["reserve_escalation"] = float(st.session_state.reserve_escalation)
    params["reserve_policy"] = str(st.session_state.reserve_policy)

    # Set recovery type for all tenants
    params["GLOBAL_RECOVERY_TYPE"] = str(st.session_state.recovery_type)
    if "lease_roll" in params:
        for tenant in params["lease_roll"]:
            tenant["recovery_type"] = str(st.session_state.recovery_type)

    # Set market growth and spread parameters
    params["market_rent_growth_min"] = float(st.session_state.market_rent_growth_min)
    params["market_rent_growth_max"] = float(st.session_state.market_rent_growth_max)
    params["rent_spread_std"] = float(st.session_state.rent_spread_std)
    params["renewal_spread_std"] = float(st.session_state.renewal_spread_std)

    # Set latent market strength parameters
    params["latent_market"] = st.session_state.latent_market.copy()

    # Set exit cap rate sampling parameters
    params["exit_cap_left"] = float(st.session_state.exit_cap_left)
    params["exit_cap_mode"] = float(st.session_state.exit_cap_mode)
    params["exit_cap_right"] = float(st.session_state.exit_cap_right)

            # Stage 2 correlations disabled in UI - functionality available through monte_carlo_model.py

    # Set exit cap rate override
    if st.session_state.exit_cap_override is not None:
        params["exit_cap_override"] = float(st.session_state.exit_cap_override)

    # Set lease roll parameters
    params["walt_years"] = float(st.session_state.walt_years)
    params["ti_psf_new"] = float(st.session_state.ti_psf_new)
    params["ti_psf_renew"] = float(st.session_state.ti_psf_renew)
    params["lc_pct_new"] = float(st.session_state.lc_pct_new)
    params["lc_pct_renew"] = float(st.session_state.lc_pct_renew)
    params["renew_prob"] = float(st.session_state.renew_prob)
    params["renew_free_months"] = (None if st.session_state.renew_free_months in (None, '') else int(st.session_state.renew_free_months))
    params["renew_downtime_months"] = (None if st.session_state.renew_downtime_months in (None, '') else int(st.session_state.renew_downtime_months))
    params["downtime_months"] = int(st.session_state.downtime_months)
    params["vacant_downtime_months"] = int(st.session_state.vacant_downtime_months)
    params["vacant_rent_psf"] = float(st.session_state.vacant_rent_psf)
    params["vacancy_absorption_pct_annual"] = float(st.session_state.vacancy_absorption_pct_annual)
    params["vacancy_months_to_stabilize"] = int(st.session_state.vacancy_months_to_stabilize)
    params["vacant_free_months_new"] = int(st.session_state.vacant_free_months_new)
    params["vacant_new_lease_term_years"] = (None if float(st.session_state.vacant_new_lease_term_years) == 0.0 else float(st.session_state.vacant_new_lease_term_years))
    params["vacancy_target_rent_psf"] = (None if float(st.session_state.vacancy_target_rent_psf) == 0.0 else float(st.session_state.vacancy_target_rent_psf))
    params["recoveries_during_free_months"] = bool(st.session_state.recoveries_during_free_months)
    params["backfill_prob"] = float(st.session_state.backfill_prob)
    params["frictional_vacancy_floor"] = float(st.session_state.frictional_vacancy_floor)
    params["in_term_bump_pct"] = float(st.session_state.in_term_bump_pct)
    params["in_term_bump_freq_years"] = int(st.session_state.in_term_bump_freq_years)

    params["_seed"] = int(seed)

    # Advanced correlations: pass through if enabled in UI
    if isinstance(st.session_state.get('correlations'), dict):
        params['correlations'] = st.session_state.correlations.copy()
    # (fallback loop handles correlations per-run below)

    if hasattr(monte_carlo_model, "run_simulation"):
        # Streamlit browser runs are kept single-process to avoid multiprocessing pipe
        # failures in long-lived demo servers while preserving the same engine inputs.
        result_df = _run_sim_cached(n=int(n), seed=int(seed), params=params, parallel=False)
        st.session_state.trace_payload = _compact_trace_payload_for_ai(result_df, params, int(seed))
        return result_df

    # Fallback loop
    irrs = []
    for i in range(int(n)):
        p = copy.deepcopy(monte_carlo_model.default_params())
        if scenario and hasattr(monte_carlo_model, "apply_scenario_overrides"):
            try:
                p = monte_carlo_model.apply_scenario_overrides(p, scenario)
            except Exception:
                pass
        p["_seed"] = int(seed) + i
        # UI-only overrides (do not edit monte_carlo_model.py)
        p["in_place_rent_psf"] = float(st.session_state.in_place_rent_psf)
        p["total_rsf"] = float(st.session_state.total_rsf)
        p["initial_occupancy"] = float(st.session_state.initial_occupancy)
        p["market_rent_psf"] = float(st.session_state.market_rent_psf)
        p["purchase_price"] = float(st.session_state.purchase_price)
        p["operating_expenses_start"] = float(st.session_state.operating_expenses_start)
        p["opex_growth_rate"] = float(st.session_state.opex_growth_rate)
        p["property_tax_rate"] = float(st.session_state.property_tax_rate)
        p["tax_mode"] = str(st.session_state.tax_mode)
        p["tax_growth_rate"] = float(st.session_state.tax_growth_rate)

        # Set tax_reassessment dictionary
        p["tax_reassessment"] = {
            "on_refi": bool(st.session_state.tax_reassess_on_refi),
            "on_sale": bool(st.session_state.tax_reassess_on_sale),
            "assessment_ratio": float(st.session_state.tax_reassess_assessment_ratio),
            "max_increase_cap_pct": float(st.session_state.tax_reassess_max_increase_cap_pct),
        }

        # Set new parameters
        p["vacancy_auto_lease"] = bool(st.session_state.vacancy_auto_lease)
        p["controllable_opex_pct"] = float(st.session_state.controllable_opex_pct)
        p["default_controllable_cap_pct"] = float(st.session_state.default_controllable_cap_pct)
        p["debt_ratio"] = float(st.session_state.debt_ratio)
        p["interest_rate"] = float(st.session_state.interest_rate)
        p["refi_year"] = int(st.session_state.refi_year)
        p["refi_cost_rate"] = float(st.session_state.refi_cost_rate)
        p["interest_only_years"] = int(st.session_state.interest_only_years)
        p["amort_years"] = int(st.session_state.amort_years)

        # Set additional new parameters
        p["post_refi_io_years"] = int(st.session_state.post_refi_io_years)
        p["discount_rate"] = float(st.session_state.discount_rate)
        p["acq_cost_rate"] = float(st.session_state.acq_cost_rate)
        p["financing_fee_rate"] = float(st.session_state.financing_fee_rate)
        p["rate_cap_cost"] = float(st.session_state.rate_cap_cost)
        p["working_capital_reserve"] = float(st.session_state.working_capital_reserve)
        p["seller_reserve_credit"] = float(st.session_state.seller_reserve_credit)
        p["contingency_reserve"] = float(st.session_state.contingency_reserve)

        # Set transfer tax parameters
        p["transfer_tax_buy_rate"] = float(st.session_state.transfer_tax_buy_rate)
        p["transfer_tax_sell_rate"] = float(st.session_state.transfer_tax_sell_rate)

        # Set working capital true-up parameters
        p["wc_true_up_close_dollar"] = float(st.session_state.wc_true_up_close_dollar)
        p["wc_true_up_close_pct_of_opex"] = float(st.session_state.wc_true_up_close_pct_of_opex)
        p["wc_true_up_sale_dollar"] = float(st.session_state.wc_true_up_sale_dollar)
        p["wc_true_up_sale_pct_of_opex"] = float(st.session_state.wc_true_up_sale_pct_of_opex)

        # Set capex and sale parameters
        p["capex_schedule"] = st.session_state.capex_schedule
        p["sale_cost_rate"] = float(st.session_state.sale_cost_rate)
        p["price_terminal_with_buyer_tax"] = bool(st.session_state.price_terminal_with_buyer_tax)
        p["sale_month"] = _demo_sale_month()

        # Set debt / covenant / refi control parameters
        p["amortization_granularity"] = str(st.session_state.amortization_granularity)
        p["covenant_track"] = bool(st.session_state.covenant_track)
        p["covenant_thresholds"] = st.session_state.covenant_thresholds.copy()
        p["covenant_action"] = str(st.session_state.covenant_action)
        p["refi_boxes"] = st.session_state.refi_boxes.copy()

        # Set lease roll parameters
        p["walt_years"] = float(st.session_state.walt_years)
        p["ti_psf_new"] = float(st.session_state.ti_psf_new)
        p["ti_psf_renew"] = float(st.session_state.ti_psf_renew)
        p["lc_pct_new"] = float(st.session_state.lc_pct_new)
        p["lc_pct_renew"] = float(st.session_state.lc_pct_renew)
        p["renew_prob"] = float(st.session_state.renew_prob)
        p["renew_free_months"] = (None if st.session_state.renew_free_months in (None, '') else int(st.session_state.renew_free_months))
        p["renew_downtime_months"] = (None if st.session_state.renew_downtime_months in (None, '') else int(st.session_state.renew_downtime_months))
        p["downtime_months"] = int(st.session_state.downtime_months)
        p["vacant_downtime_months"] = int(st.session_state.vacant_downtime_months)
        p["vacant_rent_psf"] = float(st.session_state.vacant_rent_psf)
        p["vacancy_absorption_pct_annual"] = float(st.session_state.vacancy_absorption_pct_annual)
        p["vacancy_months_to_stabilize"] = int(st.session_state.vacancy_months_to_stabilize)
        p["vacant_free_months_new"] = int(st.session_state.vacant_free_months_new)
        p["vacant_new_lease_term_years"] = (None if float(st.session_state.vacant_new_lease_term_years) == 0.0 else float(st.session_state.vacant_new_lease_term_years))
        p["vacancy_target_rent_psf"] = (None if float(st.session_state.vacancy_target_rent_psf) == 0.0 else float(st.session_state.vacancy_target_rent_psf))
        p["recoveries_during_free_months"] = bool(st.session_state.recoveries_during_free_months)
        p["backfill_prob"] = float(st.session_state.backfill_prob)
        p["frictional_vacancy_floor"] = float(st.session_state.frictional_vacancy_floor)
        p["in_term_bump_pct"] = float(st.session_state.in_term_bump_pct)
        p["in_term_bump_freq_years"] = int(st.session_state.in_term_bump_freq_years)

        # Set prepayment parameters
        p["prepay"] = st.session_state.prepay.copy()
        p["prepay_at_sale"] = bool(st.session_state.prepay_at_sale)
        p["debug_return_schedule"] = bool(st.session_state.debug_return_schedule)

        # Set reserve parameters
        p["reserve_per_rsf"] = float(st.session_state.reserve_per_rsf)
        p["reserve_start_year"] = int(st.session_state.reserve_start_year)
        p["reserve_escalation"] = float(st.session_state.reserve_escalation)
        p["reserve_policy"] = str(st.session_state.reserve_policy)

        # Set recovery type for all tenants
        p["GLOBAL_RECOVERY_TYPE"] = str(st.session_state.recovery_type)
        if "lease_roll" in p:
            for tenant in p["lease_roll"]:
                tenant["recovery_type"] = str(st.session_state.recovery_type)

        # Set market growth and spread parameters
        p["market_rent_growth_min"] = float(st.session_state.market_rent_growth_min)
        p["market_rent_growth_max"] = float(st.session_state.market_rent_growth_max)
        p["rent_spread_std"] = float(st.session_state.rent_spread_std)
        p["renewal_spread_std"] = float(st.session_state.renewal_spread_std)

        # Set latent market strength parameters
        p["latent_market"] = st.session_state.latent_market.copy()

        # Set Stage 2 correlation parameters
        if st.session_state.correlations['enabled']:
            p["correlations"] = st.session_state.correlations.copy()
        else:
            p["correlations"] = {'enabled': False}

        # Set exit cap rate override
        if st.session_state.exit_cap_override is not None:
            p["exit_cap_override"] = float(st.session_state.exit_cap_override)

        r = monte_carlo_model.run_model(p)
        irrs.append(float(r.get("IRR", float("nan"))))
    return pd.DataFrame({"IRR": irrs})

st.title("Monte Carlo Simulation Model")
st.markdown("*Professional real estate investment analysis with advanced correlation modeling*")

# Feature flag to control advanced features
SHOW_ADVANCED = False  # hide chip controls, CSV downloads, and data expanders
LIMITED_DEMO_VIEW = False
PRESERVE_ALL_SURFACES = True

VALIDATION_COPY = {
    "global": "Demo status: validated annual-model core with guarded advanced workflow surfaces.",
    "additional_kpis": "Additional KPI surfaces show currently supported contract metrics. Parked metrics are kept out of the main visible grid.",
    "covenants": "Covenant and coverage panels prefer hold-period minima when available; otherwise they stay visible with clearly labeled proxy values.",
    "trace": "Trace / Explain P50 IRR remains visible as a preserved surface. Explainability artifacts are shown only when the current runtime contract supports them.",
    "exports": "Metrics summary exports include supported fields only. Unsupported metrics stay outside the bundle until verified.",
}

_render_validation_note("info", VALIDATION_COPY["global"])

# --- Session defaults ---
for k, v in {
    "sims": 5000,
    "seed": 123,
    "stage2": False,
    "df": None,        # simulation results
    "df_hm": None,     # heatmap results
    "hm2_df": None,    # heatmap 2 results
    "ai_chat_messages": [],
    "ai_context_fingerprint": None,
    "ai_answer_style": "Short",
    "smart_scenario_profile": "Base Variation",
    "smart_scenario_seed": 2026,
    "smart_scenario_pending": None,
    "smart_scenario_last_applied": None,
    "smart_scenario_error": None,
    "trace_payload": None,
    "hm_sims": 400,    # sims per cell
    "exit_caps": ["8.5%", "8.8%", "9.0%", "9.3%", "9.8%"],
    "rent_growths": ["1.0%", "2.0%", "3.0%", "4.0%", "5.0%"],
    "scenario": "Base",
    "in_place_rent_psf": _DEFAULT_RENT_PSF,
    "total_rsf": _DEFAULT_TOTAL_RSF,
    "initial_occupancy": _DEFAULT_INITIAL_OCC,
    "market_rent_psf": _DEFAULT_MARKET_RENT,
    "purchase_price": _DEFAULT_PURCHASE_PRICE,
    "operating_expenses_start": _DEFAULT_OPEX_START,
    "opex_growth_rate": _DEFAULT_OPEX_GROWTH,
    "property_tax_rate": _DEFAULT_TAX_RATE,
    "tax_mode": _DEFAULT_TAX_MODE,
    "tax_growth_rate": _DEFAULT_TAX_GROWTH,
    # tax_reassessment parameters
    "tax_reassess_on_refi": _DEFAULT_TAX_REASSESS_ON_REFI,
    "tax_reassess_on_sale": _DEFAULT_TAX_REASSESS_ON_SALE,
    "tax_reassess_assessment_ratio": _DEFAULT_TAX_REASSESS_ASSESSMENT_RATIO,
    "tax_reassess_max_increase_cap_pct": _DEFAULT_TAX_REASSESS_MAX_INCREASE_CAP_PCT,
    # New parameters
    "vacancy_auto_lease": True,
    "controllable_opex_pct": 0.70,
    "default_controllable_cap_pct": 0.05,
    "debt_ratio": 0.50,
    "interest_rate": 0.0725,
    "refi_year": 5,
    "refi_cost_rate": 0.025,
    "interest_only_years": 2,
    "amort_years": 25,
    "recovery_type": "NNN",
    # Additional new parameters
    "post_refi_io_years": 1,
    "discount_rate": 0.105,
    "acq_cost_rate": 0.015,
    "financing_fee_rate": 0.01,
    "rate_cap_cost": 0.015,
    "working_capital_reserve": 1_000_000,
    "seller_reserve_credit": 0,
    "contingency_reserve": 1_500_000,

    # Transfer taxes
    "transfer_tax_buy_rate": 0.015,
    "transfer_tax_sell_rate": 0.01,

    # Working capital true-up
    "wc_true_up_close_dollar": 250_000,
    "wc_true_up_close_pct_of_opex": 0.055,
    "wc_true_up_sale_dollar": 150_000,
    "wc_true_up_sale_pct_of_opex": 0.025,

    # Capex and sale parameters
    "capex_schedule": {1: 500_000, 2: 300_000, 3: 200_000},
    "sale_cost_rate": 0.02,
    "price_terminal_with_buyer_tax": True,
    "sale_month": None,

    # Debt / covenant / refi controls (all default OFF; no economics change unless toggled)
    "amortization_granularity": "annual",  # 'annual' (default, current behavior) or 'monthly' (record-only; totals unchanged)
    "covenant_track": False,  # track DSCR/DY/LTV each year (warn only)
    "covenant_thresholds": {"dscr_min": 1.25, "dy_min": 0.08, "ltv_max": 0.65},  # covenant thresholds
    "covenant_action": "Warn",  # 'Warn' or 'Flag' (no cash impact)
    "refi_boxes": {"enabled": False, "lockout_years": 0, "max_ltv": 0.65, "min_dscr": 1.30, "min_dy": 0.08},  # refi qualification boxes

    # Prepayment parameters
    "prepay": {
        'model': 'defeasance',        # options: 'none','stepdown','ym','defeasance'
        'lockout_years': 0,
        'stepdown': {1: 0.05, 2: 0.04, 3: 0.03, 4: 0.02, 5: 0.01},
        'ym_spread': 0.02,           # yield-maintenance proxy spread
        'defeasance_open_year': None, # if set, stop stream at this year (e.g., last open period). None = to maturity
        'df_method': 'flat',          # 'flat' = use rf_flat_rate; 'curve' = use rf_curve per year
        'rf_flat_rate': 0.045,        # flat risk-free rate for discounting (e.g., 4.5%) - clamped to 2%-8% for realism
        'rf_curve': {1: 0.043, 2: 0.044, 3: 0.05}, # {1:0.043,2:0.044,...} optional per-year risk-free curve
        'fees_bps': 30                # admin/legal/servicer fees in bps of PV (e.g., 30 = 0.30%)
    },
    "prepay_at_sale": True,          # if True, apply prepayment penalty at sale using the same prepay model
    "debug_return_schedule": True,    # if True, include full debt schedule in results (for debugging)

    # Capex buckets / reserves (defaults keep behavior unchanged)
    "reserve_per_rsf": 0.25,         # annual replacement reserve accrual per RSF (cash outflow below NOI)
    "reserve_start_year": 1,          # first year to start accruing reserves
    "reserve_escalation": 0.03,       # annual escalation of reserve per RSF
    "reserve_policy": 'offset_building', # 'accrue_only' or 'offset_building' (use reserves to fund building capex)

    # Market rent growth and spread parameters
    "market_rent_growth_min": 0.01,   # annual market rent growth lower bound (shuffles each year)
    "market_rent_growth_max": 0.025,  # annual market rent growth upper bound (shuffles each year)
    "rent_spread_std": 0.05,         # random spread applied to mark-to-market on new deals
    "renewal_spread_std": 0.01,      # random spread applied on renewals vs market
    "exit_cap_left": 0.085,
    "exit_cap_mode": 0.090,
    "exit_cap_right": 0.0975,

    # Lease roll configuration (tenant lease structure)
    "walt_years": 7.0,               # Weighted Average Lease Term in YEARS
    "ti_psf_new": 60.0,              # Tenant improvement cost per RSF for new leases
    "ti_psf_renew": 25.0,            # Tenant improvement cost per RSF for renewals
    "lc_pct_new": 0.06,              # Leasing commission % for new leases
    "lc_pct_renew": 0.06,            # Leasing commission % for renewals
    "renew_prob": 0.60,              # Probability of lease renewal (0.0-1.0)
    # Optional renewal concessions; None = use model defaults
    "renew_free_months": None,       # when None, model uses half of new free months
    "renew_downtime_months": None,   # when None, model defaults to 0
    "downtime_months": 6,            # Months of downtime for new leases
    "vacant_downtime_months": 3,     # Months of downtime for vacancy bucket
    "vacant_rent_psf": 23.0,         # Deprecated placeholder (not used for revenue; vacancy uses market rent)
    # Vacancy lease-up controls
    "vacancy_absorption_pct_annual": 0.30,  # % of remaining vacant RSF leased per year
    "vacancy_months_to_stabilize": 0,       # If >0, evenly lease initial vacancy over N months
    "vacant_free_months_new": 3,            # Free months for new vacancy leases
    "vacant_new_lease_term_years": 0.0,     # 0 = use WALT
    "vacancy_target_rent_psf": 0.0,         # 0 = use market rent
    "recoveries_during_free_months": True,   # Count free months as occupied for recoveries (typical NNN)
    "backfill_prob": 0.97,                   # Probability that a vacant tranche backfills in a month
    "frictional_vacancy_floor": 0.03,        # Structural vacancy floor (fraction of RSF)
    "in_term_bump_pct": 0.02,                # Annual in-term rent growth
    "in_term_bump_freq_years": 1,            # Bump frequency in years

         # policy thresholds (defaults)
        "th_yoc": 0.065,   # Yield on Cost ≥ 6.5%
        "th_ltv": 0.75,    # LTV ≤ 75%
        "th_dscr": 1.25,   # DSCR ≥ 1.25x
        "th_be": 0.85,     # Breakeven Occ ≤ 85%
        "th_dy1": 0.08,    # Debt Yield (Y1) ≥ 8%
        "th_tol": 0.10,    # 10% amber tolerance

        # Latent market strength (OFF by default)
        "latent_market": {
            'enabled': False,          # keep OFF by default (no behavior change)
            'rho': -0.6,               # corr(occupancy_shock, growth_tilt) target
            'occ_mean': 0.826,         # baseline if enabled
            'occ_sigma': 0.08,         # stdev for occupancy shock (absolute, not % points)
            'occ_clamp': (0.50, 0.98), # clamp resulting occupancy into a sane band
            'tilt_pp': 0.01,           # 100 bps = 0.01
            'seed_offset': 0           # Randomness isolation (optional)
        },

        # Exit cap rate override (None = use random sampling)
        "exit_cap_override": None,  # Override random exit cap sampling (e.g., 0.085 for 8.5%)

        # Generalized correlation engine (Stage 2)
        "correlations": {
            'enabled': False,
            'variables': ['occ0', 'rg_bias'],  # minimal default (matches Stage 1 behavior)
            'matrix': [
                [ 1.0, -0.6],
                [-0.6,  1.0]
            ],
            'rate_band': None,   # e.g., (0.055, 0.085)
            'seed_offset': 0     # Optional seed offset for correlation draw
        }
}.items():
    st.session_state.setdefault(k, v)

# Tornado defaults (UI state)
for k, v in {
    'tornado_metric': 'IRR',
    'tornado_stat': 'p50',
    'tornado_n_per_case': 250,
    'tornado_seeds': '2025',
    'tornado_use_corr': False,
    'tornado_keep_override': False,
    'tornado_use_default_shocks': True,
    'tornado_use_crn': True,
    'tornado_params': [],
    'btn_build_tornado': False,
    'tornado_slow_absorption': True,
    'tornado_df': None,
}.items():
    st.session_state.setdefault(k, v)

BUILD = "preserved-surfaces-v1"
with st.expander("Developer status", expanded=False):
    st.caption(f"Build label: {BUILD}")
    st.caption("Advanced surfaces use guarded validation-state messaging.")

# Add some spacing
st.write("")
st.write("")

# --- Controls Form ---
st.header("Simulation Controls")
st.markdown("Configure your Monte Carlo simulation parameters below:")
_render_smart_scenario_generator()
st.markdown("---")

with st.form("controls"):
    # Simulation Settings Section
    st.subheader("Simulation Settings")
    col_a, col_b, col_c = st.columns([1,1,1])
    with col_a:
        sims_input = st.number_input(
            "Simulations", min_value=200, max_value=50000,
            value=st.session_state.sims, step=100, key="sims_input")
    with col_b:
        seed_input = st.number_input(
            "Seed", min_value=0, value=st.session_state.seed, step=1, key="seed_input")
    # Stage-2 Correlations checkbox removed - functionality available through monte_carlo_model.py

    # Scenario selector (keys of monte_carlo_model.SCENARIOS, default "Base")
    scen_keys = ["Base"]
    try:
        more = [k for k in getattr(monte_carlo_model, "SCENARIOS", {}).keys() if k != "Base"]
        scen_keys = ["Base"] + sorted(set(more))
    except Exception:
        pass
    scenario_input = st.selectbox("Scenario", scen_keys, 
                                  index=scen_keys.index(st.session_state.scenario) if st.session_state.scenario in scen_keys else 0)

    st.markdown("---")

    # Property Fundamentals Section
    st.subheader("Property Fundamentals")
    col_rent, col_rsf, col_occ, col_market = st.columns([1,1,1,1])
    with col_rent:
        st.session_state.in_place_rent_psf = st.number_input(
            "In-place Rent ($/RSF/YR)",
            min_value=0.0,
            max_value=500.0,
            value=float(st.session_state.in_place_rent_psf),
            step=0.25,
            format="%.2f",
            help="UI-only override for in-place rent; does not change monte_carlo_model.py defaults."
        )
    with col_rsf:
        st.session_state.total_rsf = st.number_input(
            "Total RSF",
            min_value=10000,
            max_value=2000000,
            value=int(st.session_state.total_rsf),
            step=1000,
            help="Total rentable square footage; affects lease roll structure."
        )
    with col_occ:
        st.session_state.initial_occupancy = _pct_input(
            "Initial Occupancy (%)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.initial_occupancy),
            step=0.005,
            format="%.1f",
            help="Initial occupancy rate; affects lease roll structure."
        )
    with col_market:
        st.session_state.market_rent_psf = st.number_input(
            "Market Rent ($/RSF/YR)",
            min_value=0.0,
            max_value=500.0,
            value=float(st.session_state.market_rent_psf),
            step=0.25,
            format="%.2f",
            help="Market rent for mark-to-market; affects future lease renewals."
        )

    st.markdown("---")

    # Market Growth & Spread Section
    st.subheader("Market Growth & Spread Controls")
    col_growth_min, col_growth_max, col_rent_spread, col_renewal_spread = st.columns([1,1,1,1])
    with col_growth_min:
        st.session_state.market_rent_growth_min = _pct_input(
            "Market Rent Growth Min (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.market_rent_growth_min),
            step=0.005,
            format="%.1f",
            help="Annual market rent growth lower bound (shuffles each year)."
        )
    with col_growth_max:
        st.session_state.market_rent_growth_max = _pct_input(
            "Market Rent Growth Max (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.market_rent_growth_max),
            step=0.005,
            format="%.1f",
            help="Annual market rent growth upper bound (shuffles each year)."
        )
    with col_rent_spread:
        st.session_state.rent_spread_std = _pct_input(
            "Rent Spread Std (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.rent_spread_std),
            step=0.005,
            format="%.1f",
            help="Random spread applied to mark-to-market on new deals."
        )
    with col_renewal_spread:
        st.session_state.renewal_spread_std = _pct_input(
            "Renewal Spread Std (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.renewal_spread_std),
            step=0.005,
            format="%.1f",
            help="Random spread applied on renewals vs market."
        )

    st.markdown("---")

    # Exit Cap Rate Override Section
    st.subheader("Exit Cap Rate Override")
    st.markdown("""
    **Exit Cap Rate Override** allows you to set a fixed exit cap rate instead of random sampling.
    Default: Random sampling from 8.5% to 9.75% (mode 9.0%). Override for sensitivity analysis.
    """)

    # Toggle button for enabling/disabling the override
    col_toggle, col_spacer1, col_spacer2, col_spacer3 = st.columns([1,1,1,1])
    with col_toggle:
        exit_cap_override_enabled = st.checkbox(
            "Enable Exit Cap Rate Override",
            value=st.session_state.exit_cap_override is not None,
            help="Toggle to enable/disable custom exit cap rate override"
        )

    # Exit cap rate input field (only visible when override is enabled)
    if exit_cap_override_enabled:
        col_exit_cap, col_spacer1, col_spacer2, col_spacer3 = st.columns([1,1,1,1])
        with col_exit_cap:
            # Show triangle indicator when override is active
            st.markdown("🔺 **Active Override**")
            exit_cap_input = st.number_input(
                "Exit Cap Rate Override (%)",
                min_value=5.0,
                max_value=15.0,
                value=float(st.session_state.exit_cap_override * 100.0) if st.session_state.exit_cap_override is not None else 8.5,
                step=0.1,
                format="%.1f",
                help="Override random exit cap sampling. Set custom rate for sensitivity analysis."
            )
            st.session_state.exit_cap_override = float(exit_cap_input) / 100.0
    else:
        # Disable override when checkbox is unchecked
        st.session_state.exit_cap_override = None
        st.info("Exit cap rate override is disabled. Using random sampling from triangular distribution.")

    # Exit Cap Rate Sampling Parameters Section
    st.markdown("---")
    st.subheader("Exit Cap Rate Sampling Parameters")
    st.markdown("""
    **Control the randomness** of exit cap rate sampling when override is disabled.
    These parameters define the triangular distribution used for random sampling.
    """)

    # Initialize session state for sampling parameters if not exists
    if 'exit_cap_left' not in st.session_state:
        st.session_state.exit_cap_left = 0.085
    if 'exit_cap_mode' not in st.session_state:
        st.session_state.exit_cap_mode = 0.090
    if 'exit_cap_right' not in st.session_state:
        st.session_state.exit_cap_right = 0.0975

    col_left, col_mode, col_right = st.columns(3)

    with col_left:
        left_bound = st.number_input(
            "Left Bound (%)",
            min_value=1.0,
            max_value=20.0,
            value=float(st.session_state.exit_cap_left * 100),
            step=0.1,
            format="%.1f",
            help="Minimum value of the triangular distribution (lower bound)"
        )
        st.session_state.exit_cap_left = left_bound / 100.0

    with col_mode:
        mode_value = st.number_input(
            "Mode (%)",
            min_value=1.0,
            max_value=20.0,
            value=float(st.session_state.exit_cap_mode * 100),
            step=0.1,
            format="%.1f",
            help="Most likely value (peak) of the triangular distribution"
        )
        st.session_state.exit_cap_mode = mode_value / 100.0

    with col_right:
        right_bound = st.number_input(
            "Right Bound (%)",
            min_value=1.0,
            max_value=20.0,
            value=float(st.session_state.exit_cap_right * 100),
            step=0.1,
            format="%.1f",
            help="Maximum value of the triangular distribution (upper bound)"
        )
        st.session_state.exit_cap_right = right_bound / 100.0

    # Validation and display
    left_val = st.session_state.exit_cap_left
    mode_val = st.session_state.exit_cap_mode
    right_val = st.session_state.exit_cap_right

    # Validate triangular distribution parameters
    if left_val <= mode_val <= right_val:
        st.success(f"Valid Distribution: {left_val:.1%} → {mode_val:.1%} → {right_val:.1%}")

        # Show distribution info
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric(
                "Expected Value",
                f"{((left_val + mode_val + right_val) / 3):.3%}",
                help="Mean of triangular distribution"
            )
        with col_info2:
            st.metric(
                "Range",
                f"{(right_val - left_val):.3%}",
                help="Total spread of the distribution"
            )
    else:
        st.error("❌ **Invalid Distribution**: Left ≤ Mode ≤ Right must be satisfied")
        st.info("Please adjust the parameters so that Left ≤ Mode ≤ Right")

    st.markdown("---")

    # Latent Market Strength Section
    st.subheader("Latent Market Strength")
    st.markdown("""
    **Latent Market Strength** enables correlated market shocks that simultaneously affect occupancy and rent growth.
    When enabled, each simulation run draws a latent factor that creates realistic market correlations.
    """)

    col_latent_enabled, col_latent_rho, col_latent_occ_sigma, col_latent_tilt = st.columns([1,1,1,1])
    with col_latent_enabled:
        st.session_state.latent_market['enabled'] = st.checkbox(
            "Enable Latent Market Strength",
            value=st.session_state.latent_market['enabled'],
            help="Enable correlated market shocks (occupancy + rent growth)"
        )

    if st.session_state.latent_market['enabled']:
        with col_latent_rho:
            st.session_state.latent_market['rho'] = st.number_input(
                "Correlation (ρ)",
                min_value=-0.99, max_value=0.99, value=float(st.session_state.latent_market['rho']), step=0.05, format="%.2f",
                help="Correlation between occupancy shock and growth tilt. Negative = weaker markets (higher vacancy) coincide with lower rent growth."
            )
        with col_latent_occ_sigma:
            st.session_state.latent_market['occ_sigma'] = _pct_input(
                "Occupancy Std Dev (%)",
                min_value=0.01,
                max_value=0.20,
                value=float(st.session_state.latent_market['occ_sigma']),
                step=0.005,
                format="%.1f",
                help="Standard deviation for occupancy shock."
            )
        with col_latent_tilt:
            st.session_state.latent_market['tilt_pp'] = st.number_input(
                "Growth Tilt (bps)",
                min_value=0.001, max_value=0.05, value=float(st.session_state.latent_market['tilt_pp']), step=0.001, format="%.3f",
                help="Growth tilt in percentage points. 0.01 = ±100 bps shift per year at ±1σ."
            )

        # Additional latent market controls
        col_occ_clamp_min, col_occ_clamp_max, col_seed_offset, col_spacer = st.columns([1,1,1,1])
        with col_occ_clamp_min:
            st.session_state.latent_market['occ_clamp'] = (
                st.number_input(
                    "Min Occupancy",
                    min_value=0.0, max_value=0.95, value=float(st.session_state.latent_market['occ_clamp'][0]), step=0.01, format="%.2f",
                    help="Minimum occupancy after shock (clamp to sane band)"
                ),
                st.session_state.latent_market['occ_clamp'][1]
            )
        with col_occ_clamp_max:
            st.session_state.latent_market['occ_clamp'] = (
                st.session_state.latent_market['occ_clamp'][0],
                st.number_input(
                    "Max Occupancy",
                    min_value=0.05, max_value=1.0, value=float(st.session_state.latent_market['occ_clamp'][1]), step=0.01, format="%.2f",
                    help="Maximum occupancy after shock (clamp to sane band)"
                )
            )
        with col_seed_offset:
            st.session_state.latent_market['seed_offset'] = st.number_input(
                "Seed Offset",
                min_value=0, max_value=1000, value=int(st.session_state.latent_market['seed_offset']), step=1,
                help="Randomness isolation: add to base seed for independent latent draws"
            )

    st.markdown("---")

    # Stage 2 Correlations Section (Independent from Simulation Settings)
    st.subheader("Stage 2 Correlations (Advanced)")
    st.markdown("""
    **Stage 2 Correlations** provide a generalized correlation engine for sophisticated market modeling.
    When enabled, draws correlated standard normals and maps them to target variables.
    """)

    col_corr_enabled, col_corr_vars, col_corr_seed, col_spacer = st.columns([1,1,1,1])
    with col_corr_enabled:
        st.session_state.correlations['enabled'] = st.checkbox(
            "Enable Stage 2 Correlations",
            value=st.session_state.correlations['enabled'],
            help="Enable generalized correlation matrix for advanced market modeling"
        )

    if st.session_state.correlations['enabled']:
        with col_corr_vars:
            available_vars = ['occ0', 'rg_bias', 'exit_cap_q', 'rate_q']
            selected_vars = st.multiselect(
                "Correlation Variables",
                options=available_vars,
                default=st.session_state.correlations['variables'],
                help="Select variables to correlate: occ0=occupancy, rg_bias=rent growth, exit_cap_q=exit cap, rate_q=interest rate"
            )
            st.session_state.correlations['variables'] = selected_vars

        with col_corr_seed:
            st.session_state.correlations['seed_offset'] = st.number_input(
                "Corr Seed Offset",
                min_value=0, max_value=1000, value=int(st.session_state.correlations['seed_offset']), step=1,
                help="Seed offset for correlation randomness isolation"
            )

        # Correlation matrix builder (simplified for now)
        st.markdown("**Correlation Matrix:**")
        # Initialize/edit correlation matrix sized to current variable selection
        try:
            vars_sel = list(st.session_state.correlations.get('variables', []))
        except Exception:
            vars_sel = []
        n = len(vars_sel)
        # Build a DataFrame for editing
        import pandas as _pd
        import numpy as _np
        mat = st.session_state.correlations.get('matrix', None)
        # Normalize matrix to n×n identity if missing/wrong shape
        if not isinstance(mat, list) or any(not isinstance(row, list) for row in mat) or len(mat) != n or any(len(row) != n for row in mat):
            mat = [[1.0 if i == j else (0.0) for j in range(n)] for i in range(n)]
        # Create labeled DataFrame
        df_mat = _pd.DataFrame(mat, index=vars_sel, columns=vars_sel, dtype=float)
        st.caption("Click to edit cells. Diagonal must be 1.0; matrix symmetric and PSD.")
        try:
            edited = st.data_editor(df_mat, use_container_width=True, num_rows="fixed")
        except Exception:
            # Fallback if data_editor not available
            edited = df_mat
        # Persist edited matrix back to session
        try:
            new_mat = [[float(edited.iloc[i, j]) for j in range(n)] for i in range(n)]
        except Exception:
            new_mat = mat
        st.session_state.correlations['matrix'] = new_mat

        # Validate matrix
        valid_msg = ""
        try:
            ok, msg = monte_carlo_model.validate_correlation_matrix(new_mat, vars_sel)
            if ok:
                st.success("Correlation matrix: Valid")
            else:
                st.error(f"Correlation matrix: Invalid — {msg}")
            valid_msg = ("Valid" if ok else f"Invalid: {msg}")
        except Exception as _e:
            st.warning(f"Validation unavailable: {_e}")
            valid_msg = "Validation unavailable"

        # Optional: tiny preview heatmap
        try:
            import altair as _alt
            df_heat = edited.reset_index().melt(id_vars=edited.index.name or 'index', var_name='col', value_name='val')
            df_heat = df_heat.rename(columns={edited.index.name or 'index': 'row'})
            heat = _alt.Chart(df_heat).mark_rect().encode(
                x=_alt.X('col:O', title=''), y=_alt.Y('row:O', title=''), color=_alt.Color('val:Q', scale=_alt.Scale(scheme='redblue', domain=[-1, 0, 1]))
            )
            txt = _alt.Chart(df_heat).mark_text(baseline='middle').encode(x='col:O', y='row:O', text=_alt.Text('val:Q', format='.2f'))
            st.altair_chart((heat + txt).properties(height=180), use_container_width=True)
        except Exception:
            pass

        # Interest rate band (if rate_q is selected)
        if 'rate_q' in st.session_state.correlations['variables']:
            col_rate_min, col_rate_max, col_spacer1, col_spacer2 = st.columns([1,1,1,1])
            with col_rate_min:
                rate_band_min = st.number_input(
                    "Min Interest Rate (%)",
                    min_value=0.0, max_value=15.0, value=5.5, step=0.1, format="%.1f",
                    help="Minimum interest rate when rate_q variable is used"
                )
            with col_rate_max:
                rate_band_max = st.number_input(
                    "Max Interest Rate (%)",
                    min_value=0.0, max_value=15.0, value=8.5, step=0.1, format="%.1f",
                    help="Maximum interest rate when rate_q variable is used"
                )

            if rate_band_min < rate_band_max:
                st.session_state.correlations['rate_band'] = (rate_band_min / 100.0, rate_band_max / 100.0)
            else:
                st.warning("Min rate must be less than max rate")

    st.markdown("---")

    # Financial Parameters Section
    st.subheader("Financial Parameters")
    col_price, col_opex, col_opex_growth, col_tax_rate = st.columns([1,1,1,1])
    with col_price:
        st.session_state.purchase_price = st.number_input(
            "Purchase Price ($)",
            min_value=1000000,
            max_value=1000000000,
            value=int(st.session_state.purchase_price),
            step=1000000,
            format="%d",
            help="Initial purchase price; affects equity, debt, and tax calculations."
        )
    with col_opex:
        st.session_state.operating_expenses_start = st.number_input(
            "Operating Expenses Start ($)",
            min_value=100000,
            max_value=10000000,
            value=int(st.session_state.operating_expenses_start),
            step=100000,
            format="%d",
            help="Initial annual operating expenses; affects NOI and cash flow."
        )
    with col_opex_growth:
        st.session_state.opex_growth_rate = _pct_input(
            "OPEX Growth Rate (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.opex_growth_rate),
            step=0.005,
            format="%.1f",
            help="Annual increase for operating expenses after Year 1."
        )
    with col_tax_rate:
        st.session_state.property_tax_rate = _pct_input(
            "Property Tax Rate (%)",
            min_value=0.0,
            max_value=0.10,
            value=float(st.session_state.property_tax_rate),
            step=0.001,
            format="%.1f",
            help="Effective property tax rate applied to assessed value."
        )

    st.markdown("---")

    # Tax Configuration Section
    st.subheader("Tax Configuration")
    col_tax_mode, col_tax_growth, col_spacer1, col_spacer2 = st.columns([1,1,1,1])
    with col_tax_mode:
        st.session_state.tax_mode = st.selectbox(
            "Tax Mode",
            options=["independent", "rent_indexed"],
            index=0 if st.session_state.tax_mode == "independent" else 1,
            help="How assessed value grows: 'independent' = grows at tax_growth_rate; 'rent_indexed' = follows market_rent/value_index."
        )
    with col_tax_growth:
        st.session_state.tax_growth_rate = _pct_input(
            "Tax Growth Rate (%)",
            min_value=0.0,
            max_value=0.20,
            value=float(st.session_state.tax_growth_rate),
            step=0.005,
            format="%.1f",
            help="Annual growth of assessed value (used only when tax_mode='independent')."
        )

    st.markdown("---")

    # Tax Reassessment Section
    st.subheader("Tax Reassessment Controls")
    col_tax_refi, col_tax_sale, col_tax_assessment, col_tax_cap = st.columns([1,1,1,1])
    with col_tax_refi:
        st.session_state.tax_reassess_on_refi = st.checkbox(
            "Tax Reassess on Refi",
            value=bool(st.session_state.tax_reassess_on_refi),
            help="If you refinance, the system resets your taxable value to the new appraised value."
        )
    with col_tax_sale:
        st.session_state.tax_reassess_on_sale = st.checkbox(
            "Tax Reassess on Sale",
            value=bool(st.session_state.tax_reassess_on_sale),
            help="If you sell, taxes reset for the buyer at the new appraised value."
        )
    with col_tax_assessment:
        st.session_state.tax_reassess_assessment_ratio = _pct_input(
            "Assessment Ratio (%)",
            min_value=0.0,
            max_value=2.0,
            value=float(st.session_state.tax_reassess_assessment_ratio),
            step=0.01,
            format="%.0f",
            help="Share of market value that is treated as taxable assessment."
        )
    with col_tax_cap:
        st.session_state.tax_reassess_max_increase_cap_pct = _pct_input(
            "Max Tax Increase Cap (%)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.tax_reassess_max_increase_cap_pct),
            step=0.01,
            format="%.1f",
            help="Never increase taxes by more than this amount in a single year."
        )

    st.markdown("---")

    # Lease & Recovery Section
    st.subheader("Lease & Recovery Configuration")
    col_recovery, col_vacancy, col_controllable, col_cap = st.columns([1,1,1,1])
    with col_recovery:
        st.session_state.recovery_type = st.selectbox(
            "Recovery Type",
            options=["NNN", "CAM_CAP", "BASE_YEAR"],
            index=0 if st.session_state.recovery_type == "NNN" else (1 if st.session_state.recovery_type == "CAM_CAP" else 2),
            help="NNN: Tenant pays 100% of OPEX (landlord pays nothing). CAM_CAP: Tenant pays non-controllable + controllable above cap. BASE_YEAR: Tenant pays increases above Year 1 baseline."
        )
    with col_vacancy:
        st.session_state.vacancy_auto_lease = st.checkbox(
            "Vacancy Auto-Lease",
            value=bool(st.session_state.vacancy_auto_lease),
            help="True = 'Vacant' bucket leases like others via lease_roll; False = treat as persistent vacancy (no rent/recoveries)."
        )
    with col_controllable:
        st.session_state.controllable_opex_pct = _pct_input(
            "Controllable OPEX (%)",
            min_value=0.0, max_value=1.0, value=float(st.session_state.controllable_opex_pct), step=0.01, format="%.0f",
            help="Tenant pays the rest of (1-opex)% + the cap if there was an increase; landlord pays controllable% + anything above cap."
        )
    with col_cap:
        st.session_state.default_controllable_cap_pct = _pct_input(
            "Default Controllable Cap (%)",
            min_value=0.0, max_value=0.50, value=float(st.session_state.default_controllable_cap_pct), step=0.01, format="%.1f",
            help="Lower = more tenant-friendly; higher = more landlord-friendly."
        )

    st.markdown("---")

    # Lease Roll Configuration Section
    st.subheader("Lease Roll Configuration")
    st.markdown("""
    **Lease Roll Configuration** controls how tenant leases are structured and managed throughout the hold period.
    This affects tenant improvement costs, leasing commissions, renewal probabilities, and downtime assumptions.
    """)

    # Main lease roll controls
    col_walt, col_ti_new, col_ti_renew, col_lc_new = st.columns([1,1,1,1])
    with col_walt:
        st.session_state.walt_years = st.number_input(
            "WALT (Years)",
            min_value=1.0, max_value=20.0, value=float(st.session_state.walt_years), step=0.5, format="%.1f",
            help="Weighted Average Lease Term in YEARS. Sets initial lease terms and affects renewal timing."
        )
    with col_ti_new:
        st.session_state.ti_psf_new = st.number_input(
            "TI Cost - New ($/RSF)",
            min_value=0.0, max_value=200.0, value=float(st.session_state.ti_psf_new), step=5.0, format="%.1f",
            help="Tenant improvement cost per RSF for new leases (higher than renewals)."
        )
    with col_ti_renew:
        st.session_state.ti_psf_renew = st.number_input(
            "TI Cost - Renewal ($/RSF)",
            min_value=0.0, max_value=200.0, value=float(st.session_state.ti_psf_renew), step=5.0, format="%.1f",
            help="Tenant improvement cost per RSF for lease renewals (lower than new leases)."
        )
    with col_lc_new:
        st.session_state.lc_pct_new = st.number_input(
            "LC % - New",
            min_value=0.0, max_value=20.0, value=float(st.session_state.lc_pct_new * 100.0), step=0.5, format="%.1f",
            help="Leasing commission percentage for new leases (e.g., 0.06 = 6%)."
        )
        st.session_state.lc_pct_new /= 100.0

    # Additional lease roll controls
    col_lc_renew, col_renew_prob, col_downtime, col_vacant_downtime = st.columns([1,1,1,1])
    with col_lc_renew:
        st.session_state.lc_pct_renew = st.number_input(
            "LC % - Renewal",
            min_value=0.0, max_value=20.0, value=float(st.session_state.lc_pct_renew * 100.0), step=0.5, format="%.1f",
            help="Leasing commission percentage for renewals (e.g., 0.06 = 6%)."
        )
        st.session_state.lc_pct_renew /= 100.0
    with col_renew_prob:
        st.session_state.renew_prob = _pct_input(
            "Renewal Probability (%)",
            min_value=0.0, max_value=1.0, value=float(st.session_state.renew_prob), step=0.05, format="%.0f",
            help="Probability of lease renewal. Higher = more renewals, lower = more new leases."
        )
    with col_downtime:
        st.session_state.downtime_months = st.number_input(
            "Downtime - New (Months)",
            min_value=0, max_value=24, value=int(st.session_state.downtime_months), step=1,
            help="Months of downtime for new leases (rent-free period during tenant improvements)."
        )
    with col_vacant_downtime:
        st.session_state.vacant_downtime_months = st.number_input(
            "Downtime - Vacant (Months)",
            min_value=0, max_value=24, value=int(st.session_state.vacant_downtime_months), step=1,
            help="Months of downtime for vacancy bucket (rent-free period during re-leasing)."
        )

    # Renewal-specific concessions
    col_renew_free, col_renew_dt = st.columns([1,1])
    with col_renew_free:
        st.session_state.renew_free_months = st.number_input(
            "Renewal Free Months",
            min_value=0, max_value=24,
            value=int(st.session_state.renew_free_months) if st.session_state.renew_free_months is not None else 0,
            step=1,
            help="Free months on renewal deals. If 0 and unset, model defaults to half of new free months."
        )
    with col_renew_dt:
        st.session_state.renew_downtime_months = st.number_input(
            "Renewal Downtime (Months)",
            min_value=0, max_value=12,
            value=int(st.session_state.renew_downtime_months) if st.session_state.renew_downtime_months is not None else 0,
            step=1,
            help="Downtime gap for renewals before new term commencement. If 0 and unset, defaults to 0."
        )

    # Vacancy lease-up controls
    if not LIMITED_DEMO_VIEW:
        with st.expander("Advanced lease-up controls — parked / future validation", expanded=False):
            st.caption("Retained for future validation; do not present these controls as fully validated demo drivers.")
            col_vacant_rent, col_absorb, col_stabilize, col_free = st.columns([1,1,1,1])
            with col_vacant_rent:
                st.session_state.vacant_rent_psf = st.number_input(
                    "Vacant Rent ($/SF) (display only)",
                    min_value=0.0, max_value=100.0, value=float(st.session_state.vacant_rent_psf), step=1.0, format="%.1f",
                    help="Display-only: engine ignores this for revenue; vacancy uses market rent unless a vacancy target is set."
                )
            with col_absorb:
                st.session_state.vacancy_absorption_pct_annual = _pct_input(
                    "Absorption (%/yr)",
                    min_value=0.0, max_value=1.0, value=float(st.session_state.vacancy_absorption_pct_annual), step=0.05, format="%.0f",
                    help="Percent of remaining vacant RSF leased per year (ignored if Months to Stabilize > 0)."
                )
            with col_stabilize:
                st.session_state.vacancy_months_to_stabilize = st.number_input(
                    "Months to Stabilize",
                    min_value=0, max_value=120, value=int(st.session_state.vacancy_months_to_stabilize), step=6,
                    help="If > 0, evenly lease initial vacancy over this many months."
                )
            with col_free:
                st.session_state.vacant_free_months_new = st.number_input(
                    "Vacant Free Months",
                    min_value=0, max_value=24, value=int(st.session_state.vacant_free_months_new), step=1,
                    help="Free months for new vacancy leases."
                )

            col_term, col_target_rent, col_recov_free, col_spacer = st.columns([1,1,1,1])
            with col_term:
                st.session_state.vacant_new_lease_term_years = st.number_input(
                    "Vacant New Term (yrs)",
                    min_value=0.0, max_value=30.0, value=float(st.session_state.vacant_new_lease_term_years), step=0.5, format="%.1f",
                    help="New lease term for vacancy leases. 0 = use WALT."
                )
            with col_target_rent:
                st.session_state.vacancy_target_rent_psf = st.number_input(
                    "Vacancy Target Rent ($/SF)",
                    min_value=0.0, max_value=200.0, value=float(st.session_state.vacancy_target_rent_psf), step=1.0, format="%.1f",
                    help="If > 0, use this rent for new vacancy leases instead of market rent."
                )
            with col_recov_free:
                st.session_state.recoveries_during_free_months = st.checkbox(
                    "Count Recoveries During Free Months",
                    value=bool(st.session_state.recoveries_during_free_months),
                    help="If checked, free months count toward recoveries (typical in NNN)."
                )
    # Backfill probability
    st.session_state.backfill_prob = st.slider(
        "Backfill Probability (per-month)",
        min_value=0.0, max_value=1.0, value=float(st.session_state.backfill_prob), step=0.01,
        help="Chance a vacant tranche actually leases in a given month (typical 0.95–0.98)."
    )

    # Frictional vacancy and in-term bumps
    col_floor, col_bump_pct, col_bump_freq, col_spacerX = st.columns([1,1,1,1])
    with col_floor:
        st.session_state.frictional_vacancy_floor = _pct_input(
            "Frictional Vacancy Floor (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.frictional_vacancy_floor), step=0.01, format="%.1f",
            help="Minimum structural vacancy fraction."
        )
    with col_bump_pct:
        st.session_state.in_term_bump_pct = _pct_input(
            "In-Term Bump (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.in_term_bump_pct), step=0.005, format="%.1f",
            help="Annual in-term rent escalation."
        )
    with col_bump_freq:
        st.session_state.in_term_bump_freq_years = st.number_input(
            "Bump Frequency (yrs)",
            min_value=1, max_value=5, value=int(st.session_state.in_term_bump_freq_years), step=1,
            help="Frequency of in-term rent bumps in years (e.g., 1 = annual)."
        )

    st.markdown("---")

    # Debt Structure Section
    st.subheader("Debt Structure & Financing")
    col_debt_ratio, col_interest_rate, col_refi_year, col_refi_cost = st.columns([1,1,1,1])
    with col_debt_ratio:
        st.session_state.debt_ratio = _pct_input(
            "Debt Ratio (LTV %)",
            min_value=0.0, max_value=0.75, value=float(st.session_state.debt_ratio), step=0.01, format="%.0f",
            help="Share of total cost financed by debt. Drives loan amount, interest cost, and leverage metrics."
        )
    with col_interest_rate:
        st.session_state.interest_rate = _pct_input(
            "Interest Rate (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.interest_rate), step=0.001, format="%.2f",
            help="Annual note rate on the debt, applied to the current principal balance each year."
        )
    with col_refi_year:
        st.session_state.refi_year = st.number_input(
            "Refi Year",
            min_value=0, max_value=20, value=int(st.session_state.refi_year), step=1,
            help="Attempt a refinance in model Year N (Year 1 = first modeled year). Set to 0 to fully disable refi logic."
        )
    with col_refi_cost:
        st.session_state.refi_cost_rate = _pct_input(
            "Refi Cost Rate (%)",
            min_value=0.0, max_value=0.10, value=float(st.session_state.refi_cost_rate), step=0.001, format="%.1f",
            help="Refi transaction costs as a share of the new loan. Deducted from any refi cash-out."
        )

    # Debt Structure Continued
    col_io_years, col_amort_years, col_post_refi_io, col_spacer = st.columns([1,1,1,1])
    with col_io_years:
        st.session_state.interest_only_years = st.number_input(
            "Interest Only Years",
            min_value=0, max_value=10, value=int(st.session_state.interest_only_years), step=1,
            help="Number of initial years with interest-only payments (no scheduled principal). After this, amortization begins unless refi resets IO."
        )
    with col_amort_years:
        st.session_state.amort_years = st.number_input(
            "Amortization Years",
            min_value=1, max_value=50, value=int(st.session_state.amort_years), step=1,
            help="Amortization term in YEARS used to compute the level payment when not in IO (e.g., 25-year amort schedule)."
        )
    with col_post_refi_io:
        st.session_state.post_refi_io_years = st.number_input(
            "Post-Refi IO Years",
            min_value=0, max_value=10, value=int(st.session_state.post_refi_io_years), step=1,
            help="Interest-only period AFTER a successful refi (years). 0 = none. Only takes effect if the refi actually happens."
        )

    st.markdown("---")

        # Debt Covenants & Refi Controls Section
    st.subheader("Debt Covenants & Refi Controls")

    # Add explanation of what this section does
    st.markdown("""
    **Debt Covenants** are financial requirements that borrowers must maintain to keep their loan in good standing. 
    This section lets you monitor compliance and set refinancing rules.
    """)

    # Main controls in a cleaner layout
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Covenant Monitoring**")
        st.session_state.covenant_track = st.checkbox(
            "Monitor Debt Covenants",
            value=bool(st.session_state.covenant_track),
            help="Track DSCR, Debt Yield, and LTV compliance throughout the hold period (no cash impact)"
        )

        if st.session_state.covenant_track:
            st.session_state.covenant_action = st.selectbox(
                "Violation Response",
                options=["Warn", "Flag"],
                index=0 if st.session_state.covenant_action == "Warn" else 1,
                help="Warn: Display violations only | Flag: Mark violations for review"
            )

    with col2:
        st.markdown("**Refinance Rules**")
        st.session_state.refi_boxes["enabled"] = st.checkbox(
            "Enable Refinance Rules",
            value=bool(st.session_state.refi_boxes["enabled"]),
            help="Apply qualification criteria for refinancing (DSCR, DY, LTV thresholds)"
        )

        if st.session_state.refi_boxes["enabled"]:
            st.session_state.refi_boxes["lockout_years"] = st.number_input(
                "Refinance Lockout (Years)",
                min_value=0, max_value=10, value=int(st.session_state.refi_boxes["lockout_years"]), step=1,
                help="Cannot refinance for first X years after loan origination"
            )

    with col3:
        st.markdown("**📅 Payment Schedule**")
        st.session_state.amortization_granularity = st.selectbox(
            "Payment Frequency",
            options=["annual", "monthly"],
            index=0 if st.session_state.amortization_granularity == "annual" else 1,
            help="Annual: Standard yearly payments | Monthly: Detailed monthly breakdown (record-only)"
        )

    # Covenant Thresholds (only show if monitoring is enabled)
    if st.session_state.covenant_track:
        st.markdown("---")
        st.markdown("**Covenant Thresholds**")
        st.markdown("*Set minimum acceptable values for debt covenants*")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.session_state.covenant_thresholds["dscr_min"] = st.number_input(
                "Minimum DSCR",
                min_value=0.5, max_value=3.0, value=float(st.session_state.covenant_thresholds["dscr_min"]), step=0.05, format="%.2f",
                help="Operating income must be at least this many times debt payments (≥1.25 recommended)"
            )
            st.caption("DSCR: Debt Service Coverage Ratio")

        with col2:
            st.session_state.covenant_thresholds["dy_min"] = st.number_input(
                "Minimum Debt Yield (%)",
                min_value=1.0, max_value=20.0, value=float(st.session_state.covenant_thresholds["dy_min"] * 100.0), step=0.5, format="%.1f",
                help="Annual NOI must be at least this percentage of loan balance (≥8% recommended)"
            )
            st.session_state.covenant_thresholds["dy_min"] /= 100.0
            st.caption("DY: Debt Yield")

        with col3:
            st.session_state.covenant_thresholds["ltv_max"] = st.number_input(
                "Maximum LTV (%)",
                min_value=10.0, max_value=90.0, value=float(st.session_state.covenant_thresholds["ltv_max"] * 100.0), step=5.0, format="%.0f",
                help="Loan cannot exceed this percentage of property value (≤65% recommended)"
            )
            st.session_state.covenant_thresholds["ltv_max"] /= 100.0
            st.caption("LTV: Loan-to-Value ratio")

    # Refi Qualification Boxes (only show if enabled)
    if st.session_state.refi_boxes["enabled"]:
        st.markdown("---")
        st.markdown("**Refinance Qualification Requirements**")
        st.markdown("*Criteria that must be met to qualify for refinancing*")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.session_state.refi_boxes["max_ltv"] = st.number_input(
                "Maximum LTV for Refi (%)",
                min_value=10.0, max_value=90.0, value=float(st.session_state.refi_boxes["max_ltv"] * 100.0), step=5.0, format="%.0f",
                help="Maximum loan-to-value ratio allowed for refinancing"
            )
            st.session_state.refi_boxes["max_ltv"] /= 100.0

        with col2:
            st.session_state.refi_boxes["min_dscr"] = st.number_input(
                "Minimum DSCR for Refi",
                min_value=0.5, max_value=3.0, value=float(st.session_state.refi_boxes["min_dscr"]), step=0.05, format="%.2f",
                help="Minimum debt service coverage ratio required for refinancing"
            )

        with col3:
            st.session_state.refi_boxes["min_dy"] = st.number_input(
                "Minimum Debt Yield for Refi (%)",
                min_value=1.0, max_value=20.0, value=float(st.session_state.refi_boxes["min_dy"] * 100.0), step=0.5, format="%.1f",
                help="Minimum debt yield required for refinancing"
            )
            st.session_state.refi_boxes["min_dy"] /= 100.0

    st.markdown("---")

    # Prepayment & Defeasance Controls Section
    st.subheader("Prepayment & Defeasance Controls")

    st.markdown("""
    **Prepayment penalties** protect lenders when loans are paid off early. Choose your penalty structure and 
    whether to apply it at sale. **Defeasance** is a complex prepayment method that replaces loan payments with 
    government securities.
    """)

    # Defeasance Warning
    if st.session_state.prepay.get('model') == 'defeasance':
        st.warning("""
        **Defeasance Warning**: 
        - Risk-free rates are automatically clamped to 2%-8% for realistic costs
        - Rates below 2% or above 8% will be adjusted automatically
        - Consider using NPV or CoC metrics for more stable analysis
        """)

    # Main prepayment controls
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Prepayment Model**")
        st.session_state.prepay["model"] = st.selectbox(
            "Prepayment Method",
            options=["none", "stepdown", "ym", "defeasance"],
            index=["none", "stepdown", "ym", "defeasance"].index(st.session_state.prepay["model"]),
            help="none: No penalty | stepdown: Declining % of balance | ym: Yield maintenance | defeasance: Government securities"
        )

        st.session_state.prepay["lockout_years"] = st.number_input(
            "Lockout Period (Years)",
            min_value=0, max_value=10, value=int(st.session_state.prepay["lockout_years"]), step=1,
            help="Cannot prepay for first X years (applies to all methods)"
        )

    with col2:
        st.markdown("**Prepayment Settings**")

        if st.session_state.prepay["model"] == "stepdown":
            st.markdown("*Stepdown rates (as % of balance)*")
            for year in [1, 2, 3, 4, 5]:
                if year not in st.session_state.prepay["stepdown"]:
                    st.session_state.prepay["stepdown"][year] = max(0.06 - (year - 1) * 0.01, 0.01)
                st.session_state.prepay["stepdown"][year] = st.number_input(
                    f"Year {year} Rate (%)",
                    min_value=0.0, max_value=20.0, value=float(st.session_state.prepay["stepdown"][year] * 100.0), step=0.5, format="%.1f",
                    help=f"Prepayment penalty in year {year} as % of remaining balance"
                )
                st.session_state.prepay["stepdown"][year] /= 100.0

        elif st.session_state.prepay["model"] == "ym":
            st.session_state.prepay["ym_spread"] = _pct_input(
                "Yield Maintenance Spread (%)",
                min_value=0.0, max_value=0.10, value=float(st.session_state.prepay["ym_spread"]), step=0.001, format="%.1f",
                help="Spread above the risk-free rate for yield maintenance calculation."
            )

    with col3:
        st.markdown("**Defeasance Options**")

        if st.session_state.prepay["model"] == "defeasance":
            st.session_state.prepay["defeasance_open_year"] = st.number_input(
                "Open Year (Optional)",
                min_value=1, max_value=30, value=int(st.session_state.prepay["defeasance_open_year"]) if st.session_state.prepay["defeasance_open_year"] else 30, step=1,
                help="Stop defeasance stream at this year (None = to maturity)"
            )

            # Discount Method Selection with dynamic UI updates
            discount_method = st.selectbox(
                "Discount Method",
                options=["flat", "curve"],
                index=0 if st.session_state.prepay["df_method"] == "flat" else 1,
                help="flat: Single rate | curve: Year-specific rates",
                key="discount_method_selector"
            )

            # Update session state when selection changes
            if discount_method != st.session_state.prepay["df_method"]:
                st.session_state.prepay["df_method"] = discount_method
                st.caption(f"Switched to {discount_method.upper()} method")

            # Initialize avg_curve_rate variable for method comparison
            avg_curve_rate = 0.04  # Default fallback

            # Dynamic UI based on discount method
            if st.session_state.prepay["df_method"] == "flat":
                # Flat method with visual styling
                st.divider()
                st.markdown("**Flat Rate Method**")
                st.markdown("*Single risk-free rate applied to all years*")

                flat_col1, flat_col2 = st.columns([2, 1])
                with flat_col1:
                    st.session_state.prepay["rf_flat_rate"] = _pct_input(
                        "Risk-Free Rate (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_flat_rate"]), step=0.001, format="%.2f",
                        help="Flat risk-free rate for discounting the defeasance stream."
                    )

                with flat_col2:
                    st.metric(
                        "Current Rate",
                        f"{st.session_state.prepay['rf_flat_rate']:.3%}",
                        help="This rate applies to all years in the defeasance calculation"
                    )

               

            else:  # curve method
                # Curve method with visual styling
                st.markdown("---")
                st.markdown("**Curve Method**")
                st.markdown("*Year-specific risk-free rates for more sophisticated discounting*")

                # Initialize curve if not exists
                if "rf_curve" not in st.session_state.prepay:
                    st.session_state.prepay["rf_curve"] = {}

                # Curve rate inputs in columns for better layout
                curve_col1, curve_col2, curve_col3, curve_col4, curve_col5 = st.columns(5)

                with curve_col1:
                    if 1 not in st.session_state.prepay["rf_curve"]:
                        st.session_state.prepay["rf_curve"][1] = 0.04
                    st.session_state.prepay["rf_curve"][1] = _pct_input(
                        "Year 1 (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_curve"][1]), step=0.001, format="%.2f",
                        help="Risk-free rate for year 1"
                    )

                with curve_col2:
                    if 2 not in st.session_state.prepay["rf_curve"]:
                        st.session_state.prepay["rf_curve"][2] = 0.041
                    st.session_state.prepay["rf_curve"][2] = _pct_input(
                        "Year 2 (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_curve"][2]), step=0.001, format="%.2f",
                        help="Risk-free rate for year 2"
                    )

                with curve_col3:
                    if 3 not in st.session_state.prepay["rf_curve"]:
                        st.session_state.prepay["rf_curve"][3] = 0.042
                    st.session_state.prepay["rf_curve"][3] = _pct_input(
                        "Year 3 (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_curve"][3]), step=0.001, format="%.2f",
                        help="Risk-free rate for year 3"
                    )

                with curve_col4:
                    if 4 not in st.session_state.prepay["rf_curve"]:
                        st.session_state.prepay["rf_curve"][4] = 0.043
                    st.session_state.prepay["rf_curve"][4] = _pct_input(
                        "Year 4 (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_curve"][4]), step=0.001, format="%.2f",
                        help="Risk-free rate for year 4"
                    )

                with curve_col5:
                    if 5 not in st.session_state.prepay["rf_curve"]:
                        st.session_state.prepay["rf_curve"][5] = 0.044
                    st.session_state.prepay["rf_curve"][5] = _pct_input(
                        "Year 5 (%)",
                        min_value=0.0, max_value=0.20, value=float(st.session_state.prepay["rf_curve"][5]), step=0.001, format="%.2f",
                        help="Risk-free rate for year 5"
                    )

                # Show curve summary with more years and better visualization (design banners removed per request)
                st.markdown("---")
                curve_rates = [f"Y{i}: {st.session_state.prepay['rf_curve'].get(i, 0.04):.3%}" for i in [1, 2, 3, 4, 5]]

                # Show comparison with flat rate
                if st.session_state.prepay['rf_curve']:
                    avg_curve_rate = sum(st.session_state.prepay['rf_curve'].values()) / len(st.session_state.prepay['rf_curve'])
                else:
                    avg_curve_rate = 0.04  # Default fallback
                st.metric(
                    "Average Curve Rate",
                    f"{avg_curve_rate:.3%}",
                    help="Average of all curve rates for comparison with flat rate method"
                )

            # Method comparison (minimal, calm styling)
            st.divider()
            st.caption("Method comparison")

            comp_col1, comp_col2 = st.columns(2)
            with comp_col1:
                if st.session_state.prepay["df_method"] == "flat":
                    st.caption("Flat discounting active")
                else:
                    st.caption("Flat discounting available")
                st.caption(f"Rate: {st.session_state.prepay['rf_flat_rate']:.3%} · applies to all years")

            with comp_col2:
                if st.session_state.prepay["df_method"] == "curve":
                    st.caption("Curve discounting active")
                    st.caption(f"Years 1–5 · avg {avg_curve_rate:.3%}")
                else:
                    st.caption("Curve discounting available")
                    if 'rf_curve' in st.session_state.prepay and st.session_state.prepay['rf_curve']:
                        avg_alt = sum(st.session_state.prepay['rf_curve'].values()) / len(st.session_state.prepay['rf_curve'])
                        st.caption(f"Years 1–5 · avg {avg_alt:.3%}")
                    else:
                        st.caption("Years 1–5 · avg 4.000% (default)")

            st.session_state.prepay["fees_bps"] = st.number_input(
                "Fees (Basis Points)",
                min_value=0, max_value=200, value=int(st.session_state.prepay["fees_bps"]), step=5,
                help="Admin/legal/servicer fees in basis points of present value (100 bps = 1%)"
            )

    # Prepayment at sale toggle
    st.markdown("---")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.session_state.prepay_at_sale = st.checkbox(
            "Apply Prepayment at Sale",
            value=bool(st.session_state.prepay_at_sale),
            help="Apply prepayment penalty when selling the property (uses same prepayment model)"
        )

    with col2:
        st.session_state.debug_return_schedule = st.checkbox(
            "Include Debt Schedule in Results",
            value=bool(st.session_state.debug_return_schedule),
            help="Return detailed debt payment schedule for debugging (increases result size)"
        )



    # Reserve & Capex Controls Section
    st.subheader("Reserve & Capex Controls")

    st.markdown("""
    **Replacement reserves** are annual cash set-asides for future capital improvements. 
    **Reserve policy** determines whether reserves fund building capex or just accumulate.
    """)

    # Reserve controls
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.session_state.reserve_per_rsf = st.number_input(
            "Reserve per RSF ($)",
            min_value=0.0, max_value=2.0, value=float(st.session_state.reserve_per_rsf), step=0.05, format="%.2f",
            help="Annual replacement reserve accrual per rentable square foot"
        )

    with col2:
        st.session_state.reserve_start_year = st.number_input(
            "Start Year",
            min_value=1, max_value=30, value=int(st.session_state.reserve_start_year), step=1,
            help="First year to start accruing reserves"
        )

    with col3:
        st.session_state.reserve_escalation = _pct_input(
            "Escalation Rate (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.reserve_escalation), step=0.01, format="%.1f",
            help="Annual escalation of reserve per RSF"
        )

    with col4:
        st.session_state.reserve_policy = st.selectbox(
            "Reserve Policy",
            options=["accrue_only", "offset_building"],
            index=0 if st.session_state.reserve_policy == "accrue_only" else 1,
            help="accrue_only: Just accumulate | offset_building: Fund building capex"
        )

    st.markdown("---")

    # Transfer Taxes Section
    st.subheader("Transfer Taxes")
    col_buy_tax, col_sell_tax, col_spacer1, col_spacer2 = st.columns([1,1,1,1])
    with col_buy_tax:
        st.session_state.transfer_tax_buy_rate = _pct_input(
            "Buy Transfer Tax Rate (%)",
            min_value=0.0, max_value=0.10, value=float(st.session_state.transfer_tax_buy_rate), step=0.001, format="%.1f",
            help="Transfer tax rate when purchasing the property. Set to 0 to disable."
        )
    with col_sell_tax:
        st.session_state.transfer_tax_sell_rate = _pct_input(
            "Sell Transfer Tax Rate (%)",
            min_value=0.0, max_value=0.10, value=float(st.session_state.transfer_tax_sell_rate), step=0.001, format="%.1f",
            help="Transfer tax rate when selling the property. Set to 0 to disable."
        )

    st.markdown("---")

    # Working Capital True-Up Section
    st.subheader("Working Capital True-Up")
    col_wc_close_dollar, col_wc_close_pct, col_wc_sale_dollar, col_wc_sale_pct = st.columns([1,1,1,1])
    with col_wc_close_dollar:
        st.session_state.wc_true_up_close_dollar = st.number_input(
            "WC True-Up at Close ($)",
            min_value=0, max_value=5_000_000, value=int(st.session_state.wc_true_up_close_dollar), step=50_000, format="%d",
            help="Extra cash set aside at closing for smooth operations. Increases equity needed at purchase."
        )
    with col_wc_close_pct:
        st.session_state.wc_true_up_close_pct_of_opex = _pct_input(
            "WC True-Up Close (% of OPEX)",
            min_value=0.0, max_value=0.50, value=float(st.session_state.wc_true_up_close_pct_of_opex), step=0.005, format="%.1f",
            help="Alternative: percent of first-year OPEX (annualized) applied at closing."
        )
    with col_wc_sale_dollar:
        st.session_state.wc_true_up_sale_dollar = st.number_input(
            "WC True-Up at Sale ($)",
            min_value=0, max_value=5_000_000, value=int(st.session_state.wc_true_up_sale_dollar), step=50_000, format="%d",
            help="Reserves passed to buyer at sale: 'You kept reserves for operations; pass them to me.'"
        )
    with col_wc_sale_pct:
        st.session_state.wc_true_up_sale_pct_of_opex = _pct_input(
            "WC True-Up Sale (% of OPEX)",
            min_value=0.0, max_value=0.50, value=float(st.session_state.wc_true_up_sale_pct_of_opex), step=0.005, format="%.1f",
            help="Alternative: percent of final-year OPEX for sale true-up."
        )

    st.markdown("---")

    # Capex & Sale Parameters Section
    st.subheader("Capex & Sale Parameters")
    col_sale_cost, col_buyer_tax, col_spacer = st.columns([1,1,1])
    with col_sale_cost:
        st.session_state.sale_cost_rate = _pct_input(
            "Sale Cost Rate (%)",
            min_value=0.0, max_value=0.10, value=float(st.session_state.sale_cost_rate), step=0.001, format="%.1f",
            help="Sale transaction costs as a share of sale price."
        )
    with col_buyer_tax:
        st.session_state.price_terminal_with_buyer_tax = st.checkbox(
            "Price with Buyer Tax",
            value=bool(st.session_state.price_terminal_with_buyer_tax),
            help="Should sale price reflect buyer's first-year tax after reassessment? (affects sale price significantly)"
        )

    st.markdown("---")

    # Valuation & NPV Section
    st.subheader("Valuation & NPV Parameters")
    col_discount_rate, col_spacer1, col_spacer2, col_spacer3 = st.columns([1,1,1,1])
    with col_discount_rate:
        st.session_state.discount_rate = _pct_input(
            "Discount Rate (%)",
            min_value=0.0, max_value=0.50, value=float(st.session_state.discount_rate), step=0.005, format="%.1f",
            help="Rate used to convert future cash flows into today's value."
        )

    st.markdown("---")

    # Acquisition & Financing Costs Section
    st.subheader("Acquisition & Financing Costs")
    col_acq_cost, col_financing_fee, col_rate_cap, col_spacer = st.columns([1,1,1,1])
    with col_acq_cost:
        st.session_state.acq_cost_rate = _pct_input(
            "Acquisition Cost Rate (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.acq_cost_rate), step=0.001, format="%.1f",
            help="Extra transaction costs when buying the property."
        )
    with col_financing_fee:
        st.session_state.financing_fee_rate = _pct_input(
            "Financing Fee Rate (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.financing_fee_rate), step=0.001, format="%.1f",
            help="Upfront lender fees for arranging the loan."
        )
    with col_rate_cap:
        st.session_state.rate_cap_cost = _pct_input(
            "Rate Cap Cost Rate (%)",
            min_value=0.0, max_value=0.20, value=float(st.session_state.rate_cap_cost), step=0.001, format="%.1f",
            help="Cost of buying an interest rate cap."
        )

    st.markdown("---")

    # Reserves & Working Capital Section
    st.subheader("Reserves & Working Capital")
    col_working_cap, col_seller_credit, col_contingency, col_spacer = st.columns([1,1,1,1])
    with col_working_cap:
        st.session_state.working_capital_reserve = st.number_input(
            "Working Capital Reserve ($)",
            min_value=0, max_value=10000000, value=int(st.session_state.working_capital_reserve), step=100000, format="%d",
            help="Cash set aside at closing to cover day-to-day shortfalls (like rent-up delays, expenses)."
        )
    with col_seller_credit:
        st.session_state.seller_reserve_credit = st.number_input(
            "Seller Reserve Credit ($)",
            min_value=0, max_value=10000000, value=int(st.session_state.seller_reserve_credit), step=100000, format="%d",
            help="If the seller left behind any reserves (like prepaid taxes or deposits)."
        )
    with col_contingency:
        st.session_state.contingency_reserve = st.number_input(
            "Contingency Reserve ($)",
            min_value=0, max_value=10000000, value=int(st.session_state.contingency_reserve), step=100000, format="%d",
            help="Extra pot of money held back for unexpected costs (repairs, overruns, surprises)."
        )

    st.markdown("---")

    # Calculate Button
    submitted = st.form_submit_button("🚀 Run Monte Carlo Simulation", type="primary")

    if submitted:
        # Update session state from form inputs
        st.session_state.sims = sims_input
        st.session_state.seed = seed_input
        st.session_state.scenario = scenario_input
        
        try:
            sims = int(sims_input)
            seed = int(seed_input)
        except Exception:
            sims, seed = 1000, 123
        # Workload guard: avoid accidental huge runs
        if sims > 20000:
            st.warning("Large workload — reduce simulations (≤ 20,000 recommended).")
            _app_log(f"blocked run: sims={sims} seed={seed}")
        else:
            _app_log(f"run_many:start sims={sims} seed={seed} scen={scenario_input}")
            st.session_state.trace_payload = None
            with st.spinner("Running Monte Carlo…"):
                try:
                    result_df = _run_many(sims, seed, bool(st.session_state.stage2), scenario=scenario_input)
                    st.session_state.df = result_df
                    _record_button_audit(
                        "Run Monte Carlo Simulation",
                        result_df,
                        recompute_main_metrics(result_df),
                        _main_displayed_metrics_for_audit(result_df),
                    )
                    _app_log(f"run_many:done rows={len(result_df) if result_df is not None else 0}")
                    st.success(f"✅ Simulation complete! Generated {len(result_df):,} results.")
                except Exception as e:
                    st.session_state.trace_payload = None
                    _app_log(f"run_many:error {e}")
                    st.error(f"Run failed: {e}")

    # Active Parameters Summary
    st.markdown("---")
    st.caption("**Active Parameters Summary:**")
    # Safe formatting function to handle None values
    def safe_format(value, format_spec, default=""):
        if value is None or value == "":
            return default
        try:
            if format_spec.startswith('.') or format_spec.startswith(',.'):
                # Handle percentage and decimal formatting
                if format_spec.endswith('%'):
                    return f"{float(value):{format_spec}}"
                else:
                    return f"{float(value):{format_spec}}"
            elif format_spec.startswith(','):
                # Handle comma formatting for integers
                return f"{int(value):{format_spec}}"
            else:
                return str(value)
        except (ValueError, TypeError, AttributeError):
            return default

    # Helper function to safely get session state values
    def safe_get(key, default="N/A"):
        try:
            value = st.session_state.get(key, default)
            return value if value is not None else default
        except:
            return default

    # Build caption with safe formatting
    caption_parts = [
        f"Rent: ${safe_format(st.session_state.in_place_rent_psf, ',.2f', 'N/A')}/RSF/yr",
        f"RSF: {safe_format(st.session_state.total_rsf, ',', 'N/A')}",
        f"Occ: {safe_format(st.session_state.initial_occupancy, '.1%', 'N/A')}",
        f"Market: ${safe_format(st.session_state.market_rent_psf, ',.2f', 'N/A')}/RSF/yr",
        f"Growth: {safe_format(st.session_state.market_rent_growth_min, '.1%', 'N/A')}-{safe_format(st.session_state.market_rent_growth_max, '.1%', 'N/A')}",
        f"Rent Spread: {safe_format(st.session_state.rent_spread_std, '.1%', 'N/A')}",
        f"Renewal Spread: {safe_format(st.session_state.renewal_spread_std, '.1%', 'N/A')}",
        f"Exit Cap: {'🔺 ' + safe_format(st.session_state.exit_cap_override, '.1%', '') if st.session_state.exit_cap_override else 'Random'}",
        f"Latent: {'ON' if st.session_state.latent_market.get('enabled', False) else 'OFF'}",
        f"Stage2: {'ON' if st.session_state.correlations.get('enabled', False) else 'OFF'}",
        f"Price: ${safe_format(st.session_state.purchase_price, ',', 'N/A')}",
        f"OPEX: ${safe_format(st.session_state.operating_expenses_start, ',', 'N/A')}",
        f"OPEX Growth: {safe_format(st.session_state.opex_growth_rate, '.1%', 'N/A')}",
        f"Tax Rate: {safe_format(st.session_state.property_tax_rate, '.1%', 'N/A')}",
        f"Tax Mode: {st.session_state.tax_mode or 'N/A'}",
        f"Tax Growth: {safe_format(st.session_state.tax_growth_rate, '.1%', 'N/A')}",
        f"Recovery Type: {st.session_state.recovery_type or 'N/A'}",
        f"WALT: {safe_format(st.session_state.walt_years, '.1f', 'N/A')}yr",
        f"TI New: ${safe_format(st.session_state.ti_psf_new, '.0f', 'N/A')}/RSF",
        f"TI Renew: ${safe_format(st.session_state.ti_psf_renew, '.0f', 'N/A')}/RSF",
        f"LC New: {safe_format(st.session_state.lc_pct_new, '.1%', 'N/A')}",
        f"LC Renew: {safe_format(st.session_state.lc_pct_renew, '.1%', 'N/A')}",
        f"Renew Prob: {safe_format(st.session_state.renew_prob, '.0%', 'N/A')}",
        f"Downtime: {st.session_state.downtime_months or 'N/A'}m",
        f"Debt Ratio: {safe_format(st.session_state.debt_ratio, '.1%', 'N/A')}",
        f"Interest Rate: {safe_format(st.session_state.interest_rate, '.1%', 'N/A')}",
        f"Refi Year: {st.session_state.refi_year or 'N/A'}",
        f"IO Years: {st.session_state.interest_only_years or 'N/A'}",
        f"Amort Years: {st.session_state.amort_years or 'N/A'}",
        f"Post-Refi IO: {st.session_state.post_refi_io_years or 'N/A'}",
        f"Discount Rate: {safe_format(st.session_state.discount_rate, '.1%', 'N/A')}",
        f"Acq Cost: {safe_format(st.session_state.acq_cost_rate, '.1%', 'N/A')}",
        f"Financing Fee: {safe_format(st.session_state.financing_fee_rate, '.1%', 'N/A')}",
        f"Rate Cap: {safe_format(st.session_state.rate_cap_cost, '.1%', 'N/A')}",
        f"Working Capital: ${safe_format(st.session_state.working_capital_reserve, ',', 'N/A')}",
        f"Seller Credit: ${safe_format(st.session_state.seller_reserve_credit, ',', 'N/A')}",
        f"Contingency: ${safe_format(st.session_state.contingency_reserve, ',', 'N/A')}",
        f"Buy Tax: {safe_format(st.session_state.transfer_tax_buy_rate, '.1%', 'N/A')}",
        f"Sell Tax: {safe_format(st.session_state.transfer_tax_sell_rate, '.1%', 'N/A')}",
        f"WC Close: ${safe_format(st.session_state.wc_true_up_close_dollar, ',', 'N/A')}",
        f"WC Sale: ${safe_format(st.session_state.wc_true_up_sale_dollar, ',', 'N/A')}",
        f"Sale Cost: {safe_format(st.session_state.sale_cost_rate, '.1%', 'N/A')}",
        f"Buyer Tax: {'Yes' if st.session_state.price_terminal_with_buyer_tax else 'No'}",
        f"Amort Gran: {st.session_state.amortization_granularity or 'N/A'}",
        f"Covenants: {'ON' if st.session_state.covenant_track else 'OFF'}",
        f"Refi Boxes: {'ON' if st.session_state.refi_boxes.get('enabled', False) else 'OFF'}",
        f"Prepay: {st.session_state.prepay.get('model', 'N/A')}",
        f"Prepay at Sale: {'ON' if st.session_state.prepay_at_sale else 'OFF'}",
        f"Reserves: ${safe_format(st.session_state.reserve_per_rsf, '.2f', 'N/A')}/RSF",
        f"Reserve Policy: {st.session_state.reserve_policy or 'N/A'}"
    ]

    # If Stage-2 is ON, append a short correlations summary
    try:
        if st.session_state.correlations.get('enabled', False):
            vars_sel = list(st.session_state.correlations.get('variables', []))
            mat = st.session_state.correlations.get('matrix', [])
            try:
                ok, msg = monte_carlo_model.validate_correlation_matrix(mat, vars_sel)
                corr_sum = f"Corr vars={vars_sel} · {('Valid' if ok else 'Invalid')}"
            except Exception:
                corr_sum = f"Corr vars={vars_sel}"
            caption_parts.append(corr_sum)
        st.caption(" | ".join(caption_parts))
    except Exception:
        st.caption("Parameters loaded successfully")

# Add spacing after the form
st.write("")
st.write("")

def _build_heatmap(sims_per_cell: int, seed: int, use_stage2: bool,
                   exit_caps: list[float] | None = None,
                   rent_growths: list[float] | None = None,
                   base_rent_psf: float | None = None,
                   base_total_rsf: float | None = None,
                   base_initial_occ: float | None = None,
                   base_market_rent: float | None = None,
                   base_purchase_price: float | None = None,
                   base_opex_start: float | None = None,
                   base_opex_growth: float | None = None,
                   base_tax_rate: float | None = None,
                   base_tax_mode: str | None = None,
                   base_tax_growth: float | None = None,
                   base_tax_reassess_on_refi: bool | None = None,
                   base_tax_reassess_on_sale: bool | None = None,
                   base_tax_reassess_assessment_ratio: float | None = None,
                   base_tax_reassess_max_increase_cap_pct: float | None = None,
                   base_post_refi_io_years: int | None = None,
                   base_discount_rate: float | None = None,
                   base_acq_cost_rate: float | None = None,
                   base_financing_fee_rate: float | None = None,
                   base_rate_cap_cost: float | None = None,
                   base_working_capital_reserve: float | None = None,
                   base_seller_reserve_credit: float | None = None,
                   base_contingency_reserve: float | None = None,
                   base_transfer_tax_buy_rate: float | None = None,
                   base_transfer_tax_sell_rate: float | None = None,
                   base_wc_true_up_close_dollar: float | None = None,
                   base_wc_true_up_close_pct_of_opex: float | None = None,
                   base_wc_true_up_sale_dollar: float | None = None,
                   base_wc_true_up_sale_pct_of_opex: float | None = None,
                   base_capex_schedule: dict | None = None,
                   base_sale_cost_rate: float | None = None,
                   base_price_terminal_with_buyer_tax: bool | None = None,
                   base_sale_month: int | None = None) -> pd.DataFrame:
    """Build heatmap data by sweeping Exit Cap × Rent Growth parameters."""
    # Set fixed defaults when not provided
    if exit_caps is None:
        exit_caps = [0.075, 0.080, 0.085, 0.090, 0.095]   # 7.5% → 9.5%
    if rent_growths is None:
        rent_growths = [0.010, 0.020, 0.030, 0.040, 0.050]  # 1% → 5%

    # Parse percentage strings back to floats if they're strings
    if isinstance(exit_caps[0], str):
        exit_caps_float = [float(ec.replace('%', '')) / 100.0 for ec in exit_caps]
    else:
        exit_caps_float = exit_caps

    if isinstance(rent_growths[0], str):
        rent_growths_float = [float(rg.replace('%', '')) / 100.0 for rg in rent_growths]
    else:
        rent_growths_float = rent_growths

    results = []
    total_cells = len(exit_caps_float) * len(rent_growths_float)
    cell_count = 0

    for ec in exit_caps_float:
        for rg in rent_growths_float:
            cell_count += 1
            try:
                params = copy.deepcopy(monte_carlo_model.default_params())
                params["_seed"] = int(seed) + cell_count  # Unique seed per cell
                params["market_rent_growth_min"] = rg
                params["market_rent_growth_max"] = rg
                params["exit_cap_override"] = ec
                # Apply UI overrides if provided
                if base_rent_psf is not None:
                    params["in_place_rent_psf"] = float(base_rent_psf)
                if base_total_rsf is not None:
                    params["total_rsf"] = float(base_total_rsf)
                if base_initial_occ is not None:
                    params["initial_occupancy"] = float(base_initial_occ)
                if base_market_rent is not None:
                    params["market_rent_psf"] = float(base_market_rent)
                if base_purchase_price is not None:
                    params["purchase_price"] = float(base_purchase_price)
                if base_opex_start is not None:
                    params["operating_expenses_start"] = float(base_opex_start)
                if base_opex_growth is not None:
                    params["opex_growth_rate"] = float(base_opex_growth)
                if base_tax_rate is not None:
                    params["property_tax_rate"] = float(base_tax_rate)
                if base_tax_mode is not None:
                    params["tax_mode"] = str(base_tax_mode)
                if base_tax_growth is not None:
                    params["tax_growth_rate"] = float(base_tax_growth)

                # Apply tax_reassessment overrides if provided
                if any([base_tax_reassess_on_refi is not None, base_tax_reassess_on_sale is not None,
                       base_tax_reassess_assessment_ratio is not None, base_tax_reassess_max_increase_cap_pct is not None]):
                    # Get existing tax_reassessment or create new one
                    tax_reassess = params.get("tax_reassessment", {})
                    if base_tax_reassess_on_refi is not None:
                        tax_reassess["on_refi"] = bool(base_tax_reassess_on_refi)
                    if base_tax_reassess_on_sale is not None:
                        tax_reassess["on_sale"] = bool(base_tax_reassess_on_sale)
                    if base_tax_reassess_assessment_ratio is not None:
                        tax_reassess["assessment_ratio"] = float(base_tax_reassess_assessment_ratio)
                    if base_tax_reassess_max_increase_cap_pct is not None:
                        tax_reassess["max_increase_cap_pct"] = float(base_tax_reassess_max_increase_cap_pct)
                    params["tax_reassessment"] = tax_reassess

                # Update lease_roll structure to reflect new parameters
                if "lease_roll" in params:
                    for tenant in params["lease_roll"]:
                        if tenant.get("name") == "Top10+Rest":
                            if base_rent_psf is not None:
                                tenant["rent_psf"] = float(base_rent_psf)
                            if base_total_rsf is not None and base_initial_occ is not None:
                                tenant["rsf"] = float(base_initial_occ) * float(base_total_rsf)
                        elif tenant.get("name") == "Vacant":
                            if base_total_rsf is not None and base_initial_occ is not None:
                                tenant["rsf"] = (1.0 - float(base_initial_occ)) * float(base_total_rsf)

                # Ensure heatmap uses current prepayment settings
                params["prepay"] = st.session_state.prepay.copy()
                params["prepay_at_sale"] = bool(st.session_state.prepay_at_sale)

                # Advanced correlations: pass through UI config if provided
                if isinstance(st.session_state.get('correlations'), dict):
                    params['correlations'] = st.session_state.correlations.copy()

                if use_stage2:
                    c = params.get("correlations", {})
                    c.update({"enabled": True, "variables": ["occ0", "rg_bias"], "matrix": [[1, 0.6], [0.6, 1.0]]})
                    params["correlations"] = c

                # Run simulation with timeout protection
                df = monte_carlo_model.run_simulation(n=sims_per_cell, seed=params["_seed"], params=params, parallel=False)

                # Validate results
                if df.empty or 'IRR' not in df.columns:
                    mean_irr_pct = float('nan')
                else:
                    irr_values = df['IRR'].dropna()
                    if len(irr_values) == 0:
                        mean_irr_pct = float('nan')
                    else:
                        mean_irr_pct = float(irr_values.mean()) * 100.0

            except Exception as e:
                # Log error but continue with other cells
                print(f"Warning: Cell {cell_count}/{total_cells} failed (ec={ec}, rg={rg}): {e}")
                mean_irr_pct = float('nan')

            results.append({
                "ExitCap": f"{ec*100:.1f}%",
                "RentGrowth": f"{rg*100:.1f}%",
                "IRR_pct": mean_irr_pct
            })

    return pd.DataFrame(results)

@st.cache_data(show_spinner=False)
def _build_heatmap_cached(
    sims_per_cell: int,
    seed: int,
    use_stage2: bool,
    exit_caps: list[float] | None = None,
    rent_growths: list[float] | None = None,
    base_rent_psf: float | None = None,
    base_total_rsf: float | None = None,
    base_initial_occ: float | None = None,
    base_market_rent: float | None = None,
    base_purchase_price: float | None = None,
    base_opex_start: float | None = None,
    base_opex_growth: float | None = None,
    base_tax_rate: float | None = None,
    base_tax_mode: str | None = None,
    base_tax_growth: float | None = None,
    base_tax_reassess_on_refi: bool | None = None,
    base_tax_reassess_on_sale: bool | None = None,
    base_tax_reassess_assessment_ratio: float | None = None,
    base_tax_reassess_max_increase_cap_pct: float | None = None,
    base_post_refi_io_years: int | None = None,
    base_discount_rate: float | None = None,
    base_acq_cost_rate: float | None = None,
    base_financing_fee_rate: float | None = None,
    base_rate_cap_cost: float | None = None,
    base_working_capital_reserve: float | None = None,
    base_seller_reserve_credit: float | None = None,
    base_contingency_reserve: float | None = None,
    base_transfer_tax_buy_rate: float | None = None,
    base_transfer_tax_sell_rate: float | None = None,
    base_wc_true_up_close_dollar: float | None = None,
    base_wc_true_up_close_pct_of_opex: float | None = None,
    base_wc_true_up_sale_dollar: float | None = None,
    base_wc_true_up_sale_pct_of_opex: float | None = None,
    base_capex_schedule: dict | None = None,
    base_sale_cost_rate: float | None = None,
    base_price_terminal_with_buyer_tax: bool | None = None,
    base_sale_month: int | None = None,
) -> pd.DataFrame:
    """Cached version of heatmap builder to avoid recomputation."""
    return _build_heatmap(
        sims_per_cell=sims_per_cell,
        seed=seed,
        use_stage2=use_stage2,
        exit_caps=exit_caps,
        rent_growths=rent_growths,
        base_rent_psf=base_rent_psf,
        base_total_rsf=base_total_rsf,
        base_initial_occ=base_initial_occ,
        base_market_rent=base_market_rent,
        base_purchase_price=base_purchase_price,
        base_opex_start=base_opex_start,
        base_opex_growth=base_opex_growth,
        base_tax_rate=base_tax_rate,
        base_tax_mode=base_tax_mode,
        base_tax_growth=base_tax_growth,
        base_tax_reassess_on_refi=base_tax_reassess_on_refi,
        base_tax_reassess_on_sale=base_tax_reassess_on_sale,
        base_tax_reassess_assessment_ratio=base_tax_reassess_assessment_ratio,
        base_tax_reassess_max_increase_cap_pct=base_tax_reassess_max_increase_cap_pct,
        base_post_refi_io_years=base_post_refi_io_years,
        base_discount_rate=base_discount_rate,
        base_acq_cost_rate=base_acq_cost_rate,
        base_financing_fee_rate=base_financing_fee_rate,
        base_rate_cap_cost=base_rate_cap_cost,
        base_working_capital_reserve=base_working_capital_reserve,
        base_seller_reserve_credit=base_seller_reserve_credit,
        base_contingency_reserve=base_contingency_reserve,
        base_transfer_tax_buy_rate=base_transfer_tax_buy_rate,
        base_transfer_tax_sell_rate=base_transfer_tax_sell_rate,
        base_wc_true_up_close_dollar=base_wc_true_up_close_dollar,
        base_wc_true_up_close_pct_of_opex=base_wc_true_up_close_pct_of_opex,
        base_wc_true_up_sale_dollar=base_wc_true_up_sale_dollar,
        base_wc_true_up_sale_pct_of_opex=base_wc_true_up_sale_pct_of_opex,
        base_capex_schedule=base_capex_schedule,
        base_sale_cost_rate=base_sale_cost_rate,
        base_price_terminal_with_buyer_tax=base_price_terminal_with_buyer_tax,
        base_sale_month=base_sale_month,
    )

# Helper: gather current UI params into engine params dict (subset covering tornado keys and dependencies)
def _current_params_for_engine(seed: int | None = None) -> dict:
    p = copy.deepcopy(monte_carlo_model.default_params())

    # Apply scenario overrides if available
    try:
        scen = st.session_state.get('scenario', 'Base')
        p = monte_carlo_model.apply_scenario_overrides(p, scen)
    except Exception:
        pass

    # UI-to-engine mapping (mirror _run_many where feasible)
    # Core fundamentals
    p["in_place_rent_psf"] = float(st.session_state.in_place_rent_psf)
    p["total_rsf"] = float(st.session_state.total_rsf)
    p["initial_occupancy"] = float(st.session_state.initial_occupancy)
    p["market_rent_psf"] = float(st.session_state.market_rent_psf)
    p["purchase_price"] = float(st.session_state.purchase_price)
    p["operating_expenses_start"] = float(st.session_state.operating_expenses_start)
    p["opex_growth_rate"] = float(st.session_state.opex_growth_rate)
    p["property_tax_rate"] = float(st.session_state.property_tax_rate)
    p["tax_mode"] = str(st.session_state.tax_mode)
    p["tax_growth_rate"] = float(st.session_state.tax_growth_rate)
    p["tax_reassessment"] = {
        "on_refi": bool(st.session_state.tax_reassess_on_refi),
        "on_sale": bool(st.session_state.tax_reassess_on_sale),
        "assessment_ratio": float(st.session_state.tax_reassess_assessment_ratio),
        "max_increase_cap_pct": float(st.session_state.tax_reassess_max_increase_cap_pct),
    }

    # Debt controls
    p["debt_ratio"] = float(st.session_state.debt_ratio)
    p["interest_rate"] = float(st.session_state.interest_rate)
    p["refi_year"] = int(st.session_state.refi_year)
    p["refi_cost_rate"] = float(st.session_state.refi_cost_rate)
    p["interest_only_years"] = int(st.session_state.interest_only_years)
    p["amort_years"] = int(st.session_state.amort_years)
    p["post_refi_io_years"] = int(st.session_state.post_refi_io_years)

    # Exit cap sampling band and override
    p["exit_cap_left"] = float(st.session_state.exit_cap_left)
    p["exit_cap_mode"] = float(st.session_state.exit_cap_mode)
    p["exit_cap_right"] = float(st.session_state.exit_cap_right)
    if st.session_state.exit_cap_override is not None:
        p["exit_cap_override"] = float(st.session_state.exit_cap_override)

    # Leasing & ops
    p["walt_years"] = float(st.session_state.walt_years)
    p["ti_psf_new"] = float(st.session_state.ti_psf_new)
    p["ti_psf_renew"] = float(st.session_state.ti_psf_renew)
    p["lc_pct_new"] = float(st.session_state.lc_pct_new)
    p["lc_pct_renew"] = float(st.session_state.lc_pct_renew)
    p["renew_prob"] = float(st.session_state.renew_prob)
    p["downtime_months"] = int(st.session_state.downtime_months)
    p["vacancy_absorption_pct_annual"] = float(st.session_state.vacancy_absorption_pct_annual)
    p["vacancy_months_to_stabilize"] = int(st.session_state.vacancy_months_to_stabilize)

    # Market growth & spread
    p["market_rent_growth_min"] = float(st.session_state.market_rent_growth_min)
    p["market_rent_growth_max"] = float(st.session_state.market_rent_growth_max)
    p["rent_spread_std"] = float(st.session_state.rent_spread_std)
    p["renewal_spread_std"] = float(st.session_state.renewal_spread_std)

    # Reserves & capex/sale
    p["reserve_per_rsf"] = float(st.session_state.reserve_per_rsf)
    p["reserve_start_year"] = int(st.session_state.reserve_start_year)
    p["reserve_escalation"] = float(st.session_state.reserve_escalation)
    p["reserve_policy"] = str(st.session_state.reserve_policy)
    p["capex_schedule"] = st.session_state.capex_schedule
    p["sale_cost_rate"] = float(st.session_state.sale_cost_rate)
    p["price_terminal_with_buyer_tax"] = bool(st.session_state.price_terminal_with_buyer_tax)
    p["sale_month"] = _demo_sale_month()

    # Other costs
    p["discount_rate"] = float(st.session_state.discount_rate)
    p["acq_cost_rate"] = float(st.session_state.acq_cost_rate)
    p["financing_fee_rate"] = float(st.session_state.financing_fee_rate)
    p["rate_cap_cost"] = float(st.session_state.rate_cap_cost)
    p["working_capital_reserve"] = float(st.session_state.working_capital_reserve)
    p["seller_reserve_credit"] = float(st.session_state.seller_reserve_credit)
    p["contingency_reserve"] = float(st.session_state.contingency_reserve)
    p["transfer_tax_buy_rate"] = float(st.session_state.transfer_tax_buy_rate)
    p["transfer_tax_sell_rate"] = float(st.session_state.transfer_tax_sell_rate)

    # Recovery routing
    p["GLOBAL_RECOVERY_TYPE"] = str(st.session_state.recovery_type)

    # Latent/correlations config (will be overridden by tornado toggle if desired)
    if isinstance(st.session_state.get('latent_market'), dict):
        p["latent_market"] = copy.deepcopy(st.session_state.latent_market)
    if isinstance(st.session_state.get('correlations'), dict):
        p["correlations"] = copy.deepcopy(st.session_state.correlations)

    if seed is not None:
        p["_seed"] = int(seed)
    return p

def _build_heatmap2(
    sims_per_cell: int,
    seed: int,
    use_stage2: bool,
    rate_grid: list[float] | None = None,
    ltv_grid: list[float] | None = None,
    base_rent_psf: float | None = None,
    base_total_rsf: float | None = None,
    base_initial_occ: float | None = None,
    base_market_rent: float | None = None,
    base_purchase_price: float | None = None,
    base_opex_start: float | None = None,
    base_opex_growth: float | None = None,
    base_tax_rate: float | None = None,
    base_tax_mode: str | None = None,
    base_tax_growth: float | None = None,
    base_tax_reassess_on_refi: bool | None = None,
    base_tax_reassess_on_sale: bool | None = None,
    base_tax_reassess_assessment_ratio: float | None = None,
    base_tax_reassess_max_increase_cap_pct: float | None = None,
    base_post_refi_io_years: int | None = None,
    base_discount_rate: float | None = None,
    base_acq_cost_rate: float | None = None,
    base_financing_fee_rate: float | None = None,
    base_rate_cap_cost: float | None = None,
    base_working_capital_reserve: float | None = None,
    base_seller_reserve_credit: float | None = None,
    base_contingency_reserve: float | None = None,
    base_transfer_tax_buy_rate: float | None = None,
    base_transfer_tax_sell_rate: float | None = None,
    base_wc_true_up_close_dollar: float | None = None,
    base_wc_true_up_close_pct_of_opex: float | None = None,
    base_wc_true_up_sale_dollar: float | None = None,
    base_wc_true_up_sale_pct_of_opex: float | None = None,
    base_capex_schedule: dict | None = None,
    base_sale_cost_rate: float | None = None,
    base_price_terminal_with_buyer_tax: bool | None = None,
    base_sale_month: int | None = None,
) -> pd.DataFrame:
    # Default grids (pure Python, no NumPy dependency)
    if rate_grid is None:
        # 0.8% → 8.8% in 0.4% steps (21 points)
        rate_grid = [round(0.008 + 0.004*i, 4) for i in range(21)]
    if ltv_grid is None:
        # 0% → 50% in 10% steps
        ltv_grid = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]

    rows: list[dict] = []
    idx = 0
    for ltv in ltv_grid:
        for r in rate_grid:
            p = copy.deepcopy(monte_carlo_model.default_params())
            p["_seed"] = int(seed) + idx
            idx += 1
            p["interest_rate"] = float(r)
            p["debt_ratio"]    = float(ltv)
            # Apply UI overrides if provided
            if base_rent_psf is not None:
                p["in_place_rent_psf"] = float(base_rent_psf)
            if base_total_rsf is not None:
                p["total_rsf"] = float(base_total_rsf)
            if base_initial_occ is not None:
                p["initial_occupancy"] = float(base_initial_occ)
            if base_market_rent is not None:
                p["market_rent_psf"] = float(base_market_rent)
            if base_purchase_price is not None:
                p["purchase_price"] = float(base_purchase_price)
            if base_opex_start is not None:
                p["operating_expenses_start"] = float(base_opex_start)
            if base_opex_growth is not None:
                p["opex_growth_rate"] = float(base_opex_growth)
            if base_tax_rate is not None:
                p["property_tax_rate"] = float(base_tax_rate)
            if base_tax_mode is not None:
                p["tax_mode"] = str(base_tax_mode)
            if base_tax_growth is not None:
                p["tax_growth_rate"] = float(base_tax_growth)

            # Apply additional parameter overrides if provided
            if base_post_refi_io_years is not None:
                p["post_refi_io_years"] = int(base_post_refi_io_years)
            if base_discount_rate is not None:
                p["discount_rate"] = float(base_discount_rate)
            if base_acq_cost_rate is not None:
                p["acq_cost_rate"] = float(base_acq_cost_rate)
            if base_financing_fee_rate is not None:
                p["financing_fee_rate"] = float(base_financing_fee_rate)
            if base_rate_cap_cost is not None:
                p["rate_cap_cost"] = float(base_rate_cap_cost)
            if base_working_capital_reserve is not None:
                p["working_capital_reserve"] = float(base_working_capital_reserve)
            if base_seller_reserve_credit is not None:
                p["seller_reserve_credit"] = float(base_seller_reserve_credit)
            if base_contingency_reserve is not None:
                p["contingency_reserve"] = float(base_contingency_reserve)
            if base_transfer_tax_buy_rate is not None:
                p["transfer_tax_buy_rate"] = float(base_transfer_tax_buy_rate)
            if base_transfer_tax_sell_rate is not None:
                p["transfer_tax_sell_rate"] = float(base_transfer_tax_sell_rate)
            if base_wc_true_up_close_dollar is not None:
                p["wc_true_up_close_dollar"] = float(base_wc_true_up_close_dollar)
            if base_wc_true_up_close_pct_of_opex is not None:
                p["wc_true_up_close_pct_of_opex"] = float(base_wc_true_up_close_pct_of_opex)
            if base_wc_true_up_sale_dollar is not None:
                p["wc_true_up_sale_dollar"] = float(base_wc_true_up_sale_dollar)
            if base_wc_true_up_sale_pct_of_opex is not None:
                p["wc_true_up_sale_pct_of_opex"] = float(base_wc_true_up_sale_pct_of_opex)
            if base_capex_schedule is not None:
                p["capex_schedule"] = base_capex_schedule
            if base_sale_cost_rate is not None:
                p["sale_cost_rate"] = float(base_sale_cost_rate)
            if base_price_terminal_with_buyer_tax is not None:
                p["price_terminal_with_buyer_tax"] = bool(base_price_terminal_with_buyer_tax)
            if base_sale_month is not None:
                p["sale_month"] = base_sale_month

            # Apply tax_reassessment overrides if provided
            if any([base_tax_reassess_on_refi is not None, base_tax_reassess_on_sale is not None,
                   base_tax_reassess_assessment_ratio is not None, base_tax_reassess_max_increase_cap_pct is not None]):
                # Get existing tax_reassessment or create new one
                tax_reassess = p.get("tax_reassessment", {})
                if base_tax_reassess_on_refi is not None:
                    tax_reassess["on_refi"] = bool(base_tax_reassess_on_refi)
                if base_tax_reassess_on_sale is not None:
                    tax_reassess["on_sale"] = bool(base_tax_reassess_on_sale)
                if base_tax_reassess_assessment_ratio is not None:
                    tax_reassess["assessment_ratio"] = float(base_tax_reassess_assessment_ratio)
                if base_tax_reassess_max_increase_cap_pct is not None:
                    tax_reassess["max_increase_cap_pct"] = float(base_tax_reassess_max_increase_cap_pct)
                p["tax_reassessment"] = tax_reassess

            # Update lease_roll structure to reflect new parameters
            if "lease_roll" in p:
                for tenant in p["lease_roll"]:
                    if tenant.get("name") == "Top10+Rest":
                        if base_rent_psf is not None:
                            tenant["rent_psf"] = float(base_rent_psf)
                        if base_total_rsf is not None and base_initial_occ is not None:
                            tenant["rsf"] = float(base_initial_occ) * float(base_total_rsf)
                    elif tenant.get("name") == "Vacant":
                        if base_total_rsf is not None and base_initial_occ is not None:
                            tenant["rsf"] = (1.0 - float(base_initial_occ)) * float(base_total_rsf)
            # Ensure heatmap uses current prepayment settings
            p["prepay"] = st.session_state.prepay.copy()
            p["prepay_at_sale"] = bool(st.session_state.prepay_at_sale)
            # Advanced correlations: pass through UI config if provided
            if isinstance(st.session_state.get('correlations'), dict):
                p['correlations'] = st.session_state.correlations.copy()
            if use_stage2:
                c = p.get("correlations", {})
                c.update({"enabled": True, "variables": ["occ0", "rg_bias"], "matrix": [[1, 0.6], [0.6, 1.0]]})
                p["correlations"] = c

            df_cell = monte_carlo_model.run_simulation(n=int(sims_per_cell), seed=int(p["_seed"]), params=p, parallel=False)
            irr_mean = float(df_cell["IRR"].astype(float).mean()) * 100.0

            rows.append({
                "InterestRate": f"{r*100:.1f}%",
                "DebtRatio":    f"{ltv*100:.0f}%",
                "IRR_pct":      irr_mean,
            })

    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def _build_heatmap2_cached(
    sims_per_cell: int,
    seed: int,
    use_stage2: bool,
    rate_grid: list[float] | None = None,
    ltv_grid: list[float] | None = None,
    base_rent_psf: float | None = None,
    base_total_rsf: float | None = None,
    base_initial_occ: float | None = None,
    base_market_rent: float | None = None,
    base_purchase_price: float | None = None,
    base_opex_start: float | None = None,
    base_opex_growth: float | None = None,
    base_tax_rate: float | None = None,
    base_tax_mode: str | None = None,
    base_tax_growth: float | None = None,
    base_tax_reassess_on_refi: bool | None = None,
    base_tax_reassess_on_sale: bool | None = None,
    base_tax_reassess_assessment_ratio: float | None = None,
    base_tax_reassess_max_increase_cap_pct: float | None = None,
    base_post_refi_io_years: int | None = None,
    base_discount_rate: float | None = None,
    base_acq_cost_rate: float | None = None,
    base_financing_fee_rate: float | None = None,
    base_rate_cap_cost: float | None = None,
    base_working_capital_reserve: float | None = None,
    base_seller_reserve_credit: float | None = None,
    base_contingency_reserve: float | None = None,
    base_transfer_tax_buy_rate: float | None = None,
    base_transfer_tax_sell_rate: float | None = None,
    base_wc_true_up_close_dollar: float | None = None,
    base_wc_true_up_close_pct_of_opex: float | None = None,
    base_wc_true_up_sale_dollar: float | None = None,
    base_wc_true_up_sale_pct_of_opex: float | None = None,
    base_capex_schedule: dict | None = None,
    base_sale_cost_rate: float | None = None,
    base_price_terminal_with_buyer_tax: bool | None = None,
    base_sale_month: int | None = None,
) -> pd.DataFrame:
    """Cached version of heatmap2 builder to avoid recomputation."""
    return _build_heatmap2(
        sims_per_cell, seed, use_stage2, rate_grid, ltv_grid, base_rent_psf,
        base_total_rsf, base_initial_occ, base_market_rent, base_purchase_price,
        base_opex_start, base_opex_growth, base_tax_rate, base_tax_mode, base_tax_growth,
        base_tax_reassess_on_refi, base_tax_reassess_on_sale, base_tax_reassess_assessment_ratio,
        base_tax_reassess_max_increase_cap_pct,
        base_post_refi_io_years, base_discount_rate, base_acq_cost_rate,
        base_financing_fee_rate, base_rate_cap_cost, base_working_capital_reserve,
        base_seller_reserve_credit, base_contingency_reserve,
        base_transfer_tax_buy_rate, base_transfer_tax_sell_rate,
        base_wc_true_up_close_dollar, base_wc_true_up_close_pct_of_opex,
        base_wc_true_up_sale_dollar, base_wc_true_up_sale_pct_of_opex,
        base_capex_schedule, base_sale_cost_rate, base_price_terminal_with_buyer_tax, base_sale_month,
    )

# --- Helpers (safe percentiles/formatting) ---
def _safe_pctls(series, qs=(5, 50, 95), factor=1.0):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return tuple([float("nan")] * len(qs))
    return tuple([float(np.percentile(s, q)) * factor for q in qs])

def _fmt_pct(x):  # expects decimal (e.g., 0.158 -> 15.80%)
    return "—" if (x is None or not np.isfinite(x)) else f"{x*100:.2f}%"

def _fmt_pct_value(x):  # expects already-scaled percent value
    return "—" if (x is None or not np.isfinite(x)) else f"{x:.2f}%"

def _fmt_mult(x):  # 2-decimal x
    return "—" if (x is None or not np.isfinite(x)) else f"{x:.2f}x"

# Added early to avoid NameError before later redefinitions/uses
def _fmt_money(x):  # 0-decimal money
    return "—" if (x is None or not np.isfinite(x)) else f"${x:,.0f}"

def _fmt_x(x):  # 2-decimal multiple with trailing x
    return "—" if (x is None or not np.isfinite(x)) else f"{x:.2f}x"

def _col(df, names):
    return next((n for n in names if n in df.columns), None)

# --- Render IRR Results (if available) ---
df = st.session_state.get("df")
if df is None:
    st.caption("Ready to run simulations — configure parameters above and click Run Monte Carlo Simulation.")
else:
    st.header("Simulation Results")
    st.markdown("Your Monte Carlo simulation has completed successfully. Review the results below:")

    # Add helpful explanation for covenant tracking
    if st.session_state.covenant_track:
        with st.expander("Understanding Your Results", expanded=False):
            st.markdown(f"""
            **What You're Looking At:**
            
            This simulation ran **{len(df):,} scenarios** to test how your property performs under different market conditions.
            
            **Covenant Monitoring Active:**
            - **DSCR**: Debt Service Coverage Ratio - how well operating income covers debt payments
            - **Debt Yield**: Annual NOI as a percentage of loan balance  
            - **LTV**: Loan-to-Value ratio - how much debt vs. property value
            
            **Risk Assessment:**
            - **Green (0%)**: All scenarios passed covenant tests
            - **Yellow (1-20%)**: Some risk, but manageable
            - **Red (>20%)**: High risk - consider adjusting parameters
            
            **Pro Tip**: Use the covenant controls above to adjust thresholds and see how they affect your risk profile.
            """)

    # --- IRR percentiles (in %) ---
    irr_stats = ui_metrics.irr_stats(df)
    irr_p5 = irr_stats['p5'] * 100.0 if not pd.isna(irr_stats['p5']) else float('nan')
    irr_p50 = irr_stats['p50'] * 100.0 if not pd.isna(irr_stats['p50']) else float('nan')
    irr_p95 = irr_stats['p95'] * 100.0 if not pd.isna(irr_stats['p95']) else float('nan')

    # --- PI (avg + pctls) with graceful fallback ---
    return_value_metrics = ui_metrics.return_value_metrics(df)
    pi_mean = _get(return_value_metrics, 'profitability_index', 'mean', float('nan'))
    pi_p5 = _get(return_value_metrics, 'profitability_index', 'p5', float('nan'))
    pi_p50 = _get(return_value_metrics, 'profitability_index', 'p50', float('nan'))
    pi_p95 = _get(return_value_metrics, 'profitability_index', 'p95', float('nan'))

    # --- Avg IRR (Capex-Adj.) ---
    # Keep as decimal here; later formatter converts to % to avoid double scaling
    _irr_cap_mean_raw = ui_metrics.capex_adj_irr_mean(df)
    irr_cap_mean = _irr_cap_mean_raw if not pd.isna(_irr_cap_mean_raw) else float("nan")

    # --- Min DSCR / Min DY percentiles (assume best-effort column names) ---
    covenant_metrics = ui_metrics.covenant_minima(df)
    min_dscr_p5 = covenant_metrics['min_dscr_p5']
    min_dscr_p50 = covenant_metrics['min_dscr_p50']
    min_dscr_p95 = covenant_metrics['min_dscr_p95']
    min_dy_p5 = covenant_metrics['min_dy_p5'] * 100.0 if not pd.isna(covenant_metrics['min_dy_p5']) else float("nan")
    min_dy_p50 = covenant_metrics['min_dy_p50'] * 100.0 if not pd.isna(covenant_metrics['min_dy_p50']) else float("nan")
    min_dy_p95 = covenant_metrics['min_dy_p95'] * 100.0 if not pd.isna(covenant_metrics['min_dy_p95']) else float("nan")

    # --- Most common prepay model (fallback "(n/a)") ---
    prepay_model = "(n/a)"
    try:
        col_name = "Prepay_Model" if "Prepay_Model" in df.columns else ("PrepayModel" if "PrepayModel" in df.columns else None)
        if col_name:
            mode_val = df[col_name].dropna().mode()
            if len(mode_val) > 0:
                prepay_model = str(mode_val.iat[0])
    except Exception:
        pass

    # IRR histogram (Altair) + P5 / P50 / P95 rules
    st.subheader("IRR Distribution Analysis")
    irr = pd.to_numeric(df["IRR"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if irr.empty:
        st.warning("IRR distribution is unavailable because no finite IRR values were returned.")
    else:
        df_plot = pd.DataFrame({"IRR_pct": irr * 100.0})

        # Quantiles (in percent space)
        p05 = float(irr.quantile(0.05) * 100.0)
        p50 = float(irr.quantile(0.50) * 100.0)
        p95 = float(irr.quantile(0.95) * 100.0)
        rules_df = pd.DataFrame({
            "q": [p05, p50, p95],
            "name": ["P5", "P50 (Median)", "P95"]
        })

        base = alt.Chart(df_plot)
        hist = base.mark_bar(opacity=0.75).encode(
            x=alt.X("IRR_pct:Q", bin=alt.Bin(maxbins=80), title="IRR (%)"),
            y=alt.Y("count()", title="Frequency"),
            tooltip=[alt.Tooltip("count()", title="Count")],
        )

        # Vertical rules for P5/P50/P95
        q_rules = alt.Chart(rules_df).mark_rule(size=2).encode(
            x="q:Q",
            color=alt.Color(
                "name:N",
                legend=alt.Legend(title="Quantiles"),
                # Light theme/dark theme friendly colors
                scale=alt.Scale(
                    domain=["P5", "P50 (Median)", "P95"],
                    range=["#7aa6ff", "#ffffff", "#7aa6ff"]
                ),
            ),
            tooltip=[
                alt.Tooltip("name:N", title="Quantile"),
                alt.Tooltip("q:Q", title="IRR (%)", format=".2f"),
            ],
        )

        # Optional target line at 15% (keep if you like it)
        target = alt.Chart(pd.DataFrame({"t": [15.0]})).mark_rule(
            strokeDash=[4, 3],
            color="#888"
        ).encode(x="t:Q")

        chart = (hist + q_rules + target).properties(
            width="container",
            height=360,
            title="IRR Distribution"
        )
        st.altair_chart(chart, use_container_width=True)

    # IRR P5/P50/P95 numeric chips
    st.subheader("Key IRR Metrics")
    c_irr1, c_irr2, c_irr3 = st.columns(3)
    c_irr1.metric("IRR P5",  _fmt_pct_value(irr_p5))
    c_irr2.metric("IRR P50", _fmt_pct_value(irr_p50))
    c_irr3.metric("IRR P95", _fmt_pct_value(irr_p95))

    # Alternative Metrics Section - More Stable Than IRR
    st.markdown("---")
    st.subheader("💎 Alternative Metrics (More Stable Than IRR)")
    st.markdown("""
    **Why Alternative Metrics Matter:**
    - **NPV**: Absolute dollar value, more stable than IRR
    - **CoC**: Direct cash flow measure, unaffected by defeasance complexity
    - **Equity Multiple**: Total return measure, less sensitive to timing
    """)

    # Alternative metrics in columns
    alt_cols = st.columns(4)
    alt_col1, alt_col2, alt_col3 = alt_cols[:3]
    alt_col4 = alt_cols[3]

    # Ensure NPV guard variables are defined before use in this section (from ui_metrics)
    p50_npv = _get(return_value_metrics, 'npv', 'p50')
    has_npv = p50_npv is not None and not pd.isna(p50_npv)

    # Define CoC and EM variables before use (from ui_metrics)
    coc_p50 = _get(return_value_metrics, 'coc', 'p50', float('nan'))
    has_coc = not pd.isna(coc_p50)
    em_p50 = _get(return_value_metrics, 'equity_multiple', 'p50', float('nan'))
    has_em = not pd.isna(em_p50)

    with alt_col1:
        st.metric(
            "NPV (P50)",
            _fmt_money(p50_npv) if has_npv else "—",
            help="Net Present Value at 50th percentile - more stable than IRR"
        )

    with alt_col2:
        # CoC is a decimal here; format as percentage for display
        st.metric(
            "Cash-on-Cash (P50)",
            (f"{coc_p50*100:.2f}%" if np.isfinite(coc_p50) else "—"),
            help="Annual cash return on equity - direct cash flow measure"
        )

    with alt_col3:
        st.metric(
            "Equity Multiple (P50)",
            _fmt_x(em_p50) if np.isfinite(em_p50) else "—",
            help="Total return multiple - less sensitive to timing issues"
        )

    with alt_col4:
        st.metric(
            "PI (P50)",
            _fmt_mult(pi_p50) if np.isfinite(pi_p50) else "—",
            help="Profitability Index - NPV relative to initial investment"
        )
        if not np.isfinite(pi_p50):
            st.caption("Shown for workflow completeness; not available in the current validated contract.")

    st.markdown("---")

    # --- Risk & Covenants quick flags (compact)
    st.subheader("Risk & Covenant Analysis")
    # Prefer per-run minima if present; otherwise use Year-1 values
    min_dscr_series = None
    for cand in ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr"]:
        if cand in df.columns:
            min_dscr_series = pd.to_numeric(df[cand], errors="coerce")
            break
    if min_dscr_series is None and "DSCR" in df.columns:
        min_dscr_series = pd.to_numeric(df["DSCR"], errors="coerce")

    min_dy_series = None
    for cand in ["MinDY", "MinDebtYield", "DebtYield_Min", "min_dy", "mindebtyield"]:
        if cand in df.columns:
            min_dy_series = pd.to_numeric(df[cand], errors="coerce")
            break
    if min_dy_series is None and "DebtYield_Y1" in df.columns:
        min_dy_series = pd.to_numeric(df["DebtYield_Y1"], errors="coerce")

    # WALT (yrs) if returned by the model (otherwise will show NaN)
    walt_mean = float(pd.to_numeric(df["WALT"], errors="coerce").mean()) if "WALT" in df.columns else float("nan")

    # Aggregations
    min_dscr_avg = float(min_dscr_series.mean()) if min_dscr_series is not None else float("nan")
    dscr_breach_pct = float((min_dscr_series < 1.25).mean() * 100.0) if min_dscr_series is not None else float("nan")
    min_dy_avg = float(min_dy_series.mean() * 100.0) if min_dy_series is not None else float("nan")

    # === Risk & Covenants — cards row (styled like Operations & Risk) ===
    # Helper to render a tiny colored dot + text
    def _dot(color: str) -> str:
        palette = {
            "green": "#22c55e",   # tailwind green-500
            "amber": "#f59e0b",   # tailwind amber-500
            "red":   "#ef4444",   # tailwind red-500
            "gray":  "#94a3b8",   # tailwind slate-400
        }
        return f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{palette.get(color, '#94a3b8')};margin-right:8px;vertical-align:middle'></span>"

    # Status colors
    dscr_color   = "gray" if not np.isfinite(min_dscr_avg) else ("green" if min_dscr_avg >= 1.25 else ("amber" if min_dscr_avg >= 1.15 else "red"))
    breach_color = "gray" if not np.isfinite(dscr_breach_pct) else ("green" if (dscr_breach_pct <= 0.0001) else ("amber" if dscr_breach_pct <= 5.0 else "red"))
    dy_color     = "gray" if not np.isfinite(min_dy_avg) else ("green" if min_dy_avg >= 10.0 else ("amber" if min_dy_avg >= 8.0 else "red"))
    walt_color   = "gray"   # informational
    min_dscr_source = "hold-period minimum" if any(cand in df.columns for cand in ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr"]) else ("year-1 proxy" if "DSCR" in df.columns else "unavailable")
    min_dy_source = "hold-period minimum" if any(cand in df.columns for cand in ["MinDY", "MinDebtYield", "DebtYield_Min", "min_dy", "mindebtyield"]) else ("year-1 proxy" if "DebtYield_Y1" in df.columns else "unavailable")

    _render_validation_note("info", VALIDATION_COPY["covenants"])

    c1, c2, c3, c4 = st.columns([1,1,1,1])

    with c1:
        st.markdown(
            f"**Min DSCR (avg)**  {_dot(dscr_color)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"{_fmt_mult(min_dscr_avg)}  _(rule ≥ 1.25×)_")
        st.caption(f"Source: {min_dscr_source}.")

    with c2:
        st.markdown(
            f"**% runs < 1.25×**  {_dot(breach_color)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"{_value_or_placeholder(dscr_breach_pct, lambda x: f'{x:.2f}%')}  _(target 0%)_")

    with c3:
        st.markdown(
            f"**Min DY (avg)**  {_dot(dy_color)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"{_value_or_placeholder(min_dy_avg, lambda x: f'{x:.2f}%')}  _(rule of thumb ≥ 8–10%)_")
        st.caption(f"Source: {min_dy_source}.")

    with c4:
        st.markdown(
            f"**WALT (yrs)**  {_dot(walt_color)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"{_value_or_placeholder(walt_mean, lambda x: f'{x:.2f}')}  _(input/info)_")

    st.markdown("---")

    if not LIMITED_DEMO_VIEW:
        # --- New KPIs (P5/P50/P95) ---
        st.subheader("Additional KPIs")
        _render_validation_note("info", VALIDATION_COPY["additional_kpis"])
        # Safely pull series
        def _series(name):
            return pd.to_numeric(df[name], errors="coerce") if name in df.columns else pd.Series(dtype=float)

        def _pctls(s: pd.Series):
            if s is None or s.empty:
                return float('nan'), float('nan'), float('nan')
            s = s.dropna().astype(float)
            if s.empty:
                return float('nan'), float('nan'), float('nan')
            return float(np.percentile(s, 5)), float(np.percentile(s, 50)), float(np.percentile(s, 95))

        grm_s  = _series('GRM')
        oer_s  = _series('OperatingExpenseRatio')
        e2v_s  = _series('EquityToValue')
        icr_s  = _series('InterestCoverage')
        roi_s  = _series('ROI')
        capx_s = _series('Capex_Total')

        grm_p5, grm_p50, grm_p95 = _pctls(grm_s)
        oer_p5, oer_p50, oer_p95 = _pctls(oer_s)
        e2v_p5, e2v_p50, e2v_p95 = _pctls(e2v_s)
        icr_p5, icr_p50, icr_p95 = _pctls(icr_s)
        roi_p5, roi_p50, roi_p95 = _pctls(roi_s)
        capx_p5, capx_p50, capx_p95 = _pctls(capx_s)

        visible_kpis = [
            ("GRM (P50)", grm_p50, grm_p5, grm_p95, lambda x: f"{x:.2f}"),
            ("OER (P50)", oer_p50, oer_p5, oer_p95, lambda x: f"{x:.2%}"),
            ("Equity/Value (P50)", e2v_p50, e2v_p5, e2v_p95, lambda x: f"{x:.2%}"),
            ("CapEx Total (P50)", capx_p50, capx_p5, capx_p95, _fmt_money),
        ]
        visible_kpis = [item for item in visible_kpis if _is_finite_number(item[1])]
        if visible_kpis:
            kpi_cols = st.columns(len(visible_kpis))
            for col, (label, p50_value, p5_value, p95_value, formatter) in zip(kpi_cols, visible_kpis):
                with col:
                    st.metric(label, formatter(p50_value))
                    st.caption(_range_caption(p5_value, p95_value, formatter))
        else:
            st.info("No additional KPI contract metrics are available in the current run.")

        parked_kpis = [
            ("Interest Coverage (P50)", icr_p50, icr_p5, icr_p95, lambda x: f"{x:.2f}×"),
            ("ROI Total (P50)", roi_p50, roi_p5, roi_p95, lambda x: f"{x:.2%}"),
        ]
        with st.expander("Parked metrics not included in current contract", expanded=False):
            st.caption("These cards are retained as future placeholders only; no values are fabricated.")
            parked_cols = st.columns(2)
            for col, (label, p50_value, p5_value, p95_value, formatter) in zip(parked_cols, parked_kpis):
                with col:
                    st.metric(label, _value_or_placeholder(p50_value, formatter))
                    st.caption(_range_caption(p5_value, p95_value, formatter))

        # Min DSCR & Min DY percentiles expander
        with st.expander("Risk & Covenants — Detailed Percentiles"):
            colA, colB = st.columns(2)
            with colA:
                st.markdown("**Min DSCR**")
                st.caption(_triple_caption(min_dscr_p5, min_dscr_p50, min_dscr_p95, _fmt_mult))
            with colB:
                st.markdown("**Min Debt Yield**")
                # DY is a percent
                st.caption(_triple_caption(min_dy_p5, min_dy_p50, min_dy_p95, _fmt_pct_value))

    st.markdown("---")

    # ---- BEGIN REPLACEMENT ----
    import math

    def _has(col: str) -> bool:
        return col in df.columns

    # Robust definitions with only the columns we have:
    # 1) Defeasance at refinance: share of runs where defeasance was used at refi.
    def_used_pct = float((df["Defeasance_Used"] == True).mean() * 100.0) if _has("Defeasance_Used") else 0.0

    # 2) Prepay at sale (any method): prefer using cost>0 if available; otherwise use boolean flag.
    if _has("Prepay_Cost_Sale"):
        sale_used_pct = float((df["Prepay_Cost_Sale"].astype(float) > 1e-6).mean() * 100.0)
    else:
        sale_used_pct = float((df["PrepayAtSale_Used"] == True).mean() * 100.0) if _has("PrepayAtSale_Used") else 0.0

    # 3) Average costs when used
    def_cost = float(
        df.loc[df.get("Defeasance_Used", False) == True, "Defeasance_Cost_Refi"].astype(float).mean()
    ) if _has("Defeasance_Cost_Refi") and _has("Defeasance_Used") else math.nan

    prepay_cost = float(
        df.loc[(df.get("Prepay_Cost_Sale", 0).astype(float) > 1e-6), "Prepay_Cost_Sale"].astype(float).mean()
    ) if _has("Prepay_Cost_Sale") else (
        float(df.loc[df.get("PrepayAtSale_Used", False) == True, "Prepay_Cost_Sale"].astype(float).mean())
        if _has("Prepay_Cost_Sale") and _has("PrepayAtSale_Used") else math.nan
    )

    toggle_on_pct = float((df["PrepayAtSale_Toggle"] == True).mean() * 100.0) if _has("PrepayAtSale_Toggle") else 0.0

    # Presentation helpers
    def fmt_money(x: float) -> str:
        if x != x or math.isinf(x):  # NaN/inf
            return "—"
        s = f"${abs(x):,.0f}"
        return s if x >= 0 else f"-{s}"

    def _percent_bar(label: str, pct: float, cost: float, help_text: str = ""):
        # Small title line with avg cost
        st.caption(f"**{label} — Avg cost when used: {fmt_money(cost)}**", help=help_text)
        # Progress bar with text
        st.progress(int(max(0, min(100, round(pct)))), text=f"{pct:.2f}%")

    st.subheader("Prepay / Defeasance Analysis")
    st.caption("These are independent: you may defease at a refinance and also incur a payoff at sale if debt is outstanding.")

    colA, colB = st.columns(2)
    with colA:
        _percent_bar(
            "Defeasance used at refi",
            def_used_pct,
            def_cost,
            help_text="Share of runs with defeasance used when refinancing."
        )
    with colB:
        _percent_bar(
            "Prepay at sale applied (any method)",
            sale_used_pct,
            prepay_cost,
            help_text="Share of runs with a payoff cost at sale; based on Prepay_Cost_Sale > 0 if available."
        )

    st.caption(f"'Prepay at sale' toggle ON in: {toggle_on_pct:.0f}% of runs")
    st.caption(f"Most common prepay model: {prepay_model}")
    # ---- END REPLACEMENT ----

    # Small caption under the chart: count, mean, std, min, max
    n = int(irr.shape[0])
    mean = float(irr.mean()) * 100.0
    std  = float(irr.std())  * 100.0
    vmin = float(irr.min())  * 100.0
    vmax = float(irr.max())  * 100.0
    st.caption(f"Simulation Summary: n={n:,} | mean={mean:.2f}% | std={std:.2f}% | min={vmin:.2f}% | max={vmax:.2f}%")

    st.markdown("---")

    # --- Debt Covenant Compliance Overview (if enabled) ---
    if st.session_state.covenant_track and df is not None:
        st.subheader("Debt Covenant Compliance Overview")
        st.markdown(f"*Monitoring debt covenants with action: **{st.session_state.covenant_action}***")

        # Check for covenant violation columns
        covenant_cols = [col for col in df.columns if any(x in col.lower() for x in ['covenant', 'violation', 'breach'])]

        if covenant_cols:
            st.success(f"✅ **Covenant Tracking Active** - Found {len(covenant_cols)} metric(s) being monitored")

            # Create a clear explanation of what covenants are
            with st.expander("📚 What are Debt Covenants?", expanded=False):
                st.markdown("""
                **Debt Covenants** are financial requirements that borrowers must maintain to keep their loan in good standing:
                
                - **DSCR (Debt Service Coverage Ratio)**: Operating income must be sufficient to cover debt payments
                - **Debt Yield**: Annual NOI must provide adequate return on the loan amount  
                - **LTV (Loan-to-Value)**: Loan amount cannot exceed a certain percentage of property value
                
                Violations can trigger loan default, so monitoring these metrics is crucial for risk management.
                """)

            # Show current threshold settings
            st.markdown("**Current Covenant Thresholds:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "DSCR Minimum",
                    f"{st.session_state.covenant_thresholds['dscr_min']:.2f}x",
                    help="Operating income must be at least this many times debt payments"
                )

            with col2:
                st.metric(
                    "Debt Yield Minimum",
                    f"{st.session_state.covenant_thresholds['dy_min']:.1%}",
                    help="Annual NOI must be at least this percentage of loan balance"
                )

            with col3:
                st.metric(
                    "LTV Maximum",
                    f"{st.session_state.covenant_thresholds['ltv_max']:.1%}",
                    help="Loan cannot exceed this percentage of property value"
                )

            st.markdown("---")

            # Show violation summary with clear explanations
            st.markdown("**Covenant Violation Results:**")

            for col in covenant_cols:
                if col in df.columns:
                    violations = df[col].dropna()
                    if len(violations) > 0:
                        # Determine violation type and calculate percentage
                        if violations.dtype == bool:
                            violation_pct = float((violations == True).mean() * 100.0)
                            violation_count = int(violations.sum())
                            total_runs = len(violations)
                        else:
                            violation_pct = float((violations > 0).mean() * 100.0)
                            violation_count = int((violations > 0).sum())
                            total_runs = len(violations)

                        # Create clear metric display
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            # Friendly column name
                            friendly_name = col.replace('_', ' ').replace('Covenant', '').replace('Breaches', 'Violations').replace('Count', '').strip()
                            if not friendly_name:
                                friendly_name = "Covenant Violations"

                            st.markdown(f"**{friendly_name}**")

                        with col2:
                            # Violation percentage with color coding
                            if violation_pct == 0:
                                st.success("0%")
                                st.caption("All runs compliant")
                            elif violation_pct <= 5:
                                st.warning(f"⚠️ **{violation_pct:.1f}%**")
                                st.caption("Minor risk")
                            elif violation_pct <= 20:
                                st.warning(f"⚠️ **{violation_pct:.1f}%**")
                                st.caption("Moderate risk")
                            else:
                                st.error(f"🚨 **{violation_pct:.1f}%**")
                                st.caption("High risk")

                        with col3:
                            # Raw numbers
                            st.metric(
                                "Violations",
                                f"{violation_count:,}",
                                f"of {total_runs:,} runs"
                            )

                        # Add specific explanation for each metric
                        if "Breaches_Count" in col:
                            st.info("Breach Count: Number of years during the hold period when any covenant was violated")
                        elif "First_Breach_Year" in col:
                            st.info("📅 **First Breach Year**: The earliest year when a covenant violation occurred (lower = earlier risk)")

                        st.markdown("---")

            # Overall compliance summary
            if len(covenant_cols) > 0:
                # Calculate overall compliance
                all_violations = []
                for col in covenant_cols:
                    if col in df.columns:
                        violations = df[col].dropna()
                        if len(violations) > 0:
                            if violations.dtype == bool:
                                all_violations.extend(violations.tolist())
                            else:
                                all_violations.extend((violations > 0).tolist())

                if all_violations:
                    overall_compliance = (1 - sum(all_violations) / len(all_violations)) * 100

                    st.markdown("**Overall Compliance Summary:**")
                    col1, col2 = st.columns(2)

                    with col1:
                        if overall_compliance >= 95:
                            st.success(f"🟢 **Excellent Compliance**: {overall_compliance:.1f}%")
                            st.caption("Very low covenant violation risk")
                        elif overall_compliance >= 80:
                            st.warning(f"🟡 **Good Compliance**: {overall_compliance:.1f}%")
                            st.caption("Moderate covenant violation risk")
                        else:
                            st.error(f"🔴 **Poor Compliance**: {overall_compliance:.1f}%")
                            st.caption("High covenant violation risk")

                    with col2:
                        st.metric(
                            "Compliant Runs",
                            f"{overall_compliance:.1f}%",
                            "of all simulations"
                        )

                # Action explanation
                st.markdown(f"**⚡ Action Taken**: Since you selected **{st.session_state.covenant_action}**, the system will {'display warnings' if st.session_state.covenant_action == 'Warn' else 'flag violations'} when covenants are breached.")

        else:
            st.info("📊 **Covenant tracking is enabled but no violation data found.**")
            st.markdown("""
            This could mean:
            - The model needs to be updated to track covenant metrics
            - No covenant violations occurred in any simulation runs
            - The covenant tracking columns have different names than expected
            
            **Recommended**: Check that your `monte_carlo_model.py` includes covenant tracking logic.
            """)

    st.markdown("---")

    # --- Policy Thresholds (editable) ---
    st.subheader("Policy Thresholds")
    st.markdown("Configure your underwriting criteria below:")
    with st.expander("Edit Policy Thresholds", expanded=False):
        st.session_state.th_yoc = _pct_input("Yield on Cost ≥ (%)", min_value=0.0, max_value=1.0, value=float(st.session_state.th_yoc), step=0.001, format="%.1f")
        st.session_state.th_ltv = _pct_input("LTV at Exit ≤ (%)", min_value=0.0, max_value=1.0, value=float(st.session_state.th_ltv), step=0.01, format="%.0f")
        st.session_state.th_dscr= st.number_input("DSCR (Y1) ≥",       min_value=0.0, value=float(st.session_state.th_dscr),step=0.01,  format="%.2f")
        st.session_state.th_be  = _pct_input("Breakeven Occ ≤ (%)", min_value=0.0, max_value=1.0, value=float(st.session_state.th_be), step=0.01, format="%.0f")
        st.session_state.th_dy1 = _pct_input("Debt Yield (Y1) ≥ (%)", min_value=0.0, max_value=1.0, value=float(st.session_state.th_dy1), step=0.001, format="%.1f")
        st.session_state.th_tol = _pct_input("Amber tolerance (±%)", min_value=0.0, max_value=0.50, value=float(st.session_state.th_tol), step=0.01, format="%.0f")

    st.markdown("---")

    # --- Operations & Risk -----------------------------------------------------
    st.subheader("Operations & Risk Analysis")
    NAN = float("nan")

    def s(name):
        return df[name].astype(float) if name in df.columns else None

    def mean_or_nan(sv):
        return float(sv.mean()) if (sv is not None and len(sv) > 0) else NAN

    # pull series
    yoc   = mean_or_nan(s("YieldOnCost"))
    capr  = mean_or_nan(s("CapRate"))                 # info only
    ltv   = mean_or_nan(s("LTV"))
    dscr  = mean_or_nan(s("DSCR"))                    # Year-1 proxy if MinDSCR missing
    beocc = mean_or_nan(s("BreakEvenOcc"))
    dy1   = mean_or_nan(s("DebtYield_Y1"))
    styoc = mean_or_nan(s("Stabilized_YoC"))          # info only
    stable_pct = float(s("RunStableAllYears").mean()*100) if "RunStableAllYears" in df.columns else NAN
    yrs_lt_be   = mean_or_nan(s("YearsBelowBreakeven"))

    # thresholds
    rules = {
        "YoC":   ("ge", float(st.session_state.th_yoc), yoc),
        "LTV":   ("le", float(st.session_state.th_ltv), ltv),
        "DSCR":  ("ge", float(st.session_state.th_dscr), dscr),
        "BE Occ":("le", float(st.session_state.th_be),  beocc),
        "DY1":   ("ge", float(st.session_state.th_dy1), dy1),
    }

    def status(op, target, val, tol: float = None):
        tol = float(st.session_state.th_tol) if tol is None else float(tol)
        if not (val == val):  # NaN check
            return "⚪", "n/a"
        if op == "ge":
            if val >= target:            return "🟢", "pass"
            if val >= target * (1 - tol): return "🟠", "close"
            return "🔴", "fail"
        if op == "le":
            if val <= target:            return "🟢", "pass"
            if val <= target * (1 + tol): return "🟠", "close"
            return "🔴", "fail"
        return "⚪", "n/a"

    def fmt_pct(x):   return f"{x*100:.2f}%" if x == x else "—"
    def fmt_x(x):     return f"{x:.2f}x"     if x == x else "—"

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        dot, lab = status(*rules["YoC"][:2], rules["YoC"][2])
        st.markdown(f"**Yield on Cost** {dot}<br/>{fmt_pct(yoc)} "
                    f"<span style='opacity:.7'> (rule ≥ {st.session_state.th_yoc:.1%})</span>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"**Cap Rate (info)**<br/>{fmt_pct(capr)}", unsafe_allow_html=True)
    with c3:
        dot, lab = status(*rules["LTV"][:2], rules["LTV"][2])
        st.markdown(f"**LTV at Exit** {dot}<br/>{fmt_pct(ltv)} "
                    f"<span style='opacity:.7'>(rule ≤ {st.session_state.th_ltv:.0%})</span>", unsafe_allow_html=True)
    with c4:
        dot, lab = status(*rules["DSCR"][:2], rules["DSCR"][2])
        st.markdown(f"**DSCR (Y1)** {dot}<br/>{fmt_x(dscr)} "
                    f"<span style='opacity:.7'>(rule ≥ {st.session_state.th_dscr:.2f}x)</span>", unsafe_allow_html=True)

    c5,c6,c7,c8 = st.columns(4)
    with c5:
        dot, lab = status(*rules["BE Occ"][:2], rules["BE Occ"][2])
        st.markdown(f"**Breakeven Occ** {dot}<br/>{fmt_pct(beocc)} "
                    f"<span style='opacity:.7'>(rule ≤ {st.session_state.th_be:.0%})</span>", unsafe_allow_html=True)
    with c6:
        dot, lab = status(*rules["DY1"][:2], rules["DY1"][2])
        st.markdown(f"**Debt Yield (Y1)** {dot}<br/>{fmt_pct(dy1)} "
                    f"<span style='opacity:.7'>(rule ≥ {st.session_state.th_dy1:.1%})</span>", unsafe_allow_html=True)
    with c7:
        st.markdown(f"**Stabilized YoC (info)**<br/>{fmt_pct(styoc)}", unsafe_allow_html=True)
    with c8:
        stable_display = f"{stable_pct:.2f}%" if np.isfinite(stable_pct) else "—"
        yrs_lt_be_display = f"{yrs_lt_be:.2f}" if np.isfinite(yrs_lt_be) else "—"
        st.markdown(f"**Runs Stable All Years**<br/>{stable_display}<br/>"
                    f"**Avg Years < Breakeven**: {yrs_lt_be_display}",
                    unsafe_allow_html=True)
        if not (np.isfinite(stable_pct) and np.isfinite(yrs_lt_be)):
            st.caption("Stability metrics remain visible; unavailable values reflect the current runtime contract.")
    st.divider()

    # --- Additional Metrics — Return & Value
    st.subheader("💎 Additional Return & Value Metrics")

    def _badge(text: str, bg: str) -> str:
        return f'<span style="padding:2px 10px;border-radius:999px;background:{bg};color:#111;font-weight:700;">{text}</span>'

    def _status(value: float, threshold: float, mode: str = ">=", tol: float = 0.10):
        """
        Returns (icon_text, bg_color) based on pass/near/fail vs threshold.
        tol=10% means 'amber' if within 10% of the rule boundary.
        """
        if value is None or np.isnan(value):
            return ("N/A", "#7f8c8d")
        if mode == ">=":
            if value >= threshold:
                return ("✅", "#2ecc71")   # green
            elif value >= threshold * (1 - tol):
                return ("🟡", "#f1c40f")   # amber
            else:
                return ("🔴", "#e74c3c")   # red
        else:  # mode == "<="
            if value <= threshold:
                return ("✅", "#2ecc71")
            elif value <= threshold * (1 + tol):
                return ("🟡", "#f1c40f")
            else:
                return ("🔴", "#e74c3c")

    def _pctls(series: pd.Series):
        s = series.astype(float)
        p5, p50, p95 = np.percentile(s, [5, 50, 95])
        return float(p5), float(p50), float(p95)

    # Use the unified percent formatters defined earlier
    def _fmt_money(x: float) -> str: return f"${x:,.0f}"
    def _fmt_x(x: float) -> str:     return f"{x:.2f}x"

    # Use canonical ui_metrics functions instead of direct pandas operations
    return_metrics = ui_metrics.return_value_metrics(df)

    # Define NAN constant for this block
    NAN = float('nan')

    # Extract from nested structure using _get helper
    coc_mean = _get(return_metrics, 'coc', 'mean', NAN)
    coc_p5 = _get(return_metrics, 'coc', 'p5', NAN)
    coc_p50 = _get(return_metrics, 'coc', 'p50', NAN)
    coc_p95 = _get(return_metrics, 'coc', 'p95', NAN)

    em_mean = _get(return_metrics, 'equity_multiple', 'mean', NAN)
    em_p5 = _get(return_metrics, 'equity_multiple', 'p5', NAN)
    em_p50 = _get(return_metrics, 'equity_multiple', 'p50', NAN)
    em_p95 = _get(return_metrics, 'equity_multiple', 'p95', NAN)

    npv_mean = _get(return_metrics, 'npv', 'mean', NAN)
    npv_p5 = _get(return_metrics, 'npv', 'p5', NAN)
    npv_p50 = _get(return_metrics, 'npv', 'p50', NAN)
    npv_p95 = _get(return_metrics, 'npv', 'p95', NAN)

    # Status chips
    coc_icon, coc_bg = _status(coc_mean, 0.08, mode=">=")  # CoC ≥ 8%
    em_icon,  em_bg  = _status(em_mean, 1.80, mode=">=")  # Equity Multiple ≥ 1.8x

    # Decide availability from the *computed* PI summary (may come from fallback)
    pi_available = np.isfinite(pi_mean)

    # Layout: 3–4 cards in a row
    show_pi_card = True
    cols = st.columns(4 if show_pi_card else 3)

    with cols[0]:
        st.markdown("""
        <div style="padding:12px 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.02);">
          <div style="font-size:.9rem;color:#9aa4af;">Avg Cash-on-Cash</div>
          <div style="font-size:1.4rem;font-weight:700;margin:4px 0 6px 0;">{main}</div>
          <div>{badge}</div>
          <div style="margin-top:8px;color:#9aa4af;font-size:.85rem;">P5 {p5} • P50 {p50} • P95 {p95}</div>
        </div>
        """.format(
            main=_fmt_pct(coc_mean) if np.isfinite(coc_mean) else "—",
            badge=_badge(coc_icon, coc_bg),
            p5=_fmt_pct(coc_p5) if np.isfinite(coc_p5) else "—",
            p50=_fmt_pct(coc_p50) if np.isfinite(coc_p50) else "—",
            p95=_fmt_pct(coc_p95) if np.isfinite(coc_p95) else "—",
        ), unsafe_allow_html=True)

    with cols[1]:
        st.markdown("""
        <div style="padding:12px 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.02);">
          <div style="font-size:.9rem;color:#9aa4af;">Avg Equity Multiple</div>
          <div style="font-size:1.4rem;font-weight:700;margin:4px 0 6px 0;">{main}</div>
          <div>{badge}</div>
          <div style="margin-top:8px;color:#9aa4af;font-size:.85rem;">P5 {p5} • P50 {p50} • P95 {p95}</div>
        </div>
        """.format(
            main=_fmt_x(em_mean) if np.isfinite(em_mean) else "—",
            badge=_badge(em_icon, em_bg),
            p5=_fmt_x(em_p5) if np.isfinite(em_p5) else "—",
            p50=_fmt_x(em_p50) if np.isfinite(em_p50) else "—",
            p95=_fmt_x(em_p95) if np.isfinite(em_p95) else "—",
        ), unsafe_allow_html=True)

    with cols[2]:
        st.markdown("""
        <div style="padding:12px 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.02);">
          <div style="font-size:.9rem;color:#9aa4af;">Avg NPV</div>
          <div style="font-size:1.4rem;font-weight:700;margin:4px 0 6px 0;">{main}</div>
          <div style="margin-top:8px;color:#9aa4af;font-size:.85rem;">P5 {p5} • P50 {p50} • P95 {p95}</div>
        </div>
        """.format(
            main=_fmt_money(npv_mean) if np.isfinite(npv_mean) else "—",
            p5=_fmt_money(npv_p5) if np.isfinite(npv_p5) else "—",
            p50=_fmt_money(npv_p50) if np.isfinite(npv_p50) else "—",
            p95=_fmt_money(npv_p95) if np.isfinite(npv_p95) else "—",
        ), unsafe_allow_html=True)

    # PI card (only if available)
    if show_pi_card:
        with cols[3]:
            st.markdown("""
                <div style="padding:12px 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.02);">
                  <div style="font-size:.9rem;color:#9aa4af;">Avg PI</div>
                  <div style="font-size:1.4rem;font-weight:700;margin:4px 0 6px 0;">{main}</div>
                  <div style="margin-top:8px;color:#9aa4af;font-size:.85rem;">P5 {p5} • P50 {p50} • P95 {p95}</div>
                </div>
            """.format(
                main=_fmt_mult(pi_mean),
                p5=_fmt_mult(pi_p5) if np.isfinite(pi_p5) else "—",
                p50=_fmt_mult(pi_p50) if np.isfinite(pi_p50) else "—",
                p95=_fmt_mult(pi_p95) if np.isfinite(pi_p95) else "—",
            ), unsafe_allow_html=True)

    # --- KPI strip (under histogram) ---
    st.markdown("---")
    st.subheader("Key Performance Indicators")
    # Use already calculated IRR stats from ui_metrics
    mean_irr = irr_stats['mean'] * 100.0 if not pd.isna(irr_stats['mean']) else float('nan')
    med_irr  = irr_stats['median'] * 100.0 if not pd.isna(irr_stats['median']) else float('nan')
    p95_irr  = irr_stats['p95'] * 100.0 if not pd.isna(irr_stats['p95']) else float('nan')
    prob_irr15 = irr_stats['prob_ge_15'] * 100.0 if not pd.isna(irr_stats['prob_ge_15']) else float('nan')

    # NPV may not always be present; handle gracefully using ui_metrics
    p50_npv = _get(return_value_metrics, 'npv', 'p50')
    has_npv = p50_npv is not None and not pd.isna(p50_npv)

    # Occupancy aggregates
    phys_occ_mean = float(pd.to_numeric(df.get("PhysicalOccupancyRate", pd.Series(dtype=float)), errors='coerce').mean()) if "PhysicalOccupancyRate" in df.columns else float('nan')
    econ_occ_mean = float(pd.to_numeric(df.get("EconomicOccupancyRate", pd.Series(dtype=float)), errors='coerce').mean()) if "EconomicOccupancyRate" in df.columns else float('nan')

    kpi_cards = [
        ("Mean IRR", _value_or_placeholder(mean_irr, lambda x: f"{x:.2f}%"), "Average IRR across all simulations."),
        ("Median IRR", _value_or_placeholder(med_irr, lambda x: f"{x:.2f}%"), "50th percentile (median) IRR."),
        ("P(IRR ≥ 15%)", _value_or_placeholder(prob_irr15, lambda x: f"{x:.2f}%"), "Share of simulations with IRR at least 15%."),
        ("P95 IRR", _value_or_placeholder(p95_irr, lambda x: f"{x:.2f}%"), "95th percentile IRR (only 5% of runs exceed this)."),
    ]
    if has_npv:
        kpi_cards.append(
            ("P50 NPV", _value_or_placeholder(p50_npv, lambda x: f"${x:,.0f}"), "Median Net Present Value across all simulations.")
        )
    kpi_cards.append(
        ("Avg IRR (Capex-Adj.)", _fmt_pct(irr_cap_mean), "Currently equals IRR; capex adjustment not applied.")
    )
    if np.isfinite(phys_occ_mean):
        kpi_cards.append(
            ("Physical Occupancy (Avg)", f"{phys_occ_mean*100.0:.2f}%", "Physical = RSF×occupied months / (total RSF×12)")
        )
    else:
        kpi_cards.append(
            ("Physical Occupancy (Avg)", "—", "Physical occupancy remains visible; unavailable values reflect the current runtime contract.")
        )
    if np.isfinite(econ_occ_mean):
        kpi_cards.append(
            ("Economic Occupancy (Avg)", f"{econ_occ_mean*100.0:.2f}%", "Economic = cash base rent / scheduled contract rent")
        )
    else:
        kpi_cards.append(
            ("Economic Occupancy (Avg)", "—", "Economic occupancy remains visible only when supported by the current runtime contract.")
        )

    cols = st.columns(len(kpi_cards))
    for col, (label, value, help_text) in zip(cols, kpi_cards):
        col.metric(label, value, help=help_text)

    # Results table
    if SHOW_ADVANCED:
        with st.expander("Results Table (first 1,000 rows)"):
            st.dataframe(df.head(1000))

    st.markdown("---")

# --- Heatmap Section ---
st.header("Sensitivity Analysis Heatmaps")
st.markdown("Explore directional scenario sensitivity views for headline return outcomes.")

# Heatmap 1: Exit Cap × Rent Growth
st.subheader("Heatmap 1: Exit Cap × Rent Growth Sensitivity")
st.caption("Scenario sensitivity view: compare directional IRR outcomes across an exit-cap and rent-growth grid.")

# Sims per cell slider
st.session_state.hm_sims = st.slider(
    "Simulations per cell", min_value=100, max_value=2000,
    value=st.session_state.hm_sims, step=100, key="hm_sims_slider",
    help="More simulations = smoother values but slower computation."
)

if st.button("Build Heatmap 1", key="btn_heatmap"):
    with st.spinner("Computing heatmap 1... This may take a few minutes depending on your simulation count."):
        st.session_state.df_hm = _build_heatmap_cached(
            int(st.session_state.hm_sims),
            int(st.session_state.seed),
            bool(st.session_state.stage2),
            base_rent_psf=float(st.session_state.in_place_rent_psf),
            base_total_rsf=float(st.session_state.total_rsf),
            base_initial_occ=float(st.session_state.initial_occupancy),
            base_market_rent=float(st.session_state.market_rent_psf),
            base_purchase_price=float(st.session_state.purchase_price),
            base_opex_start=float(st.session_state.operating_expenses_start),
            base_opex_growth=float(st.session_state.opex_growth_rate),
            base_tax_rate=float(st.session_state.property_tax_rate),
            base_tax_mode=str(st.session_state.tax_mode),
            base_tax_growth=float(st.session_state.tax_growth_rate),
            base_tax_reassess_on_refi=bool(st.session_state.tax_reassess_on_refi),
            base_tax_reassess_on_sale=bool(st.session_state.tax_reassess_on_sale),
            base_tax_reassess_assessment_ratio=float(st.session_state.tax_reassess_assessment_ratio),
            base_tax_reassess_max_increase_cap_pct=float(st.session_state.tax_reassess_max_increase_cap_pct),
            base_post_refi_io_years=int(st.session_state.post_refi_io_years),
            base_discount_rate=float(st.session_state.discount_rate),
            base_acq_cost_rate=float(st.session_state.acq_cost_rate),
            base_financing_fee_rate=float(st.session_state.financing_fee_rate),
            base_rate_cap_cost=float(st.session_state.rate_cap_cost),
            base_working_capital_reserve=float(st.session_state.working_capital_reserve),
            base_seller_reserve_credit=float(st.session_state.seller_reserve_credit),
            base_contingency_reserve=float(st.session_state.contingency_reserve),
            base_transfer_tax_buy_rate=float(st.session_state.transfer_tax_buy_rate),
            base_transfer_tax_sell_rate=float(st.session_state.transfer_tax_sell_rate),
            base_wc_true_up_close_dollar=float(st.session_state.wc_true_up_close_dollar),
            base_wc_true_up_close_pct_of_opex=float(st.session_state.wc_true_up_close_pct_of_opex),
            base_wc_true_up_sale_dollar=float(st.session_state.wc_true_up_sale_dollar),
            base_wc_true_up_sale_pct_of_opex=float(st.session_state.wc_true_up_sale_pct_of_opex),
            base_capex_schedule=st.session_state.capex_schedule,
            base_sale_cost_rate=float(st.session_state.sale_cost_rate),
            base_price_terminal_with_buyer_tax=bool(st.session_state.price_terminal_with_buyer_tax),
            base_sale_month=_demo_sale_month(),
        )
        _record_button_audit(
            "Build Heatmap 1",
            st.session_state.df_hm,
            recompute_heatmap_metrics(st.session_state.df_hm),
            _heatmap_displayed_metrics_for_audit(st.session_state.df_hm),
        )

# --- Render Heatmap (if available) ---
df_hm = st.session_state.get("df_hm")
if df_hm is not None and not df_hm.empty:
    # Validate heatmap data
    if len(df_hm) > 0 and all(col in df_hm.columns for col in ['ExitCap', 'RentGrowth', 'IRR_pct']):
        irr_pct_series = pd.to_numeric(df_hm["IRR_pct"], errors="coerce")
        hm1_min = float(irr_pct_series.min()) if not irr_pct_series.isna().all() else float("nan")
        hm1_max = float(irr_pct_series.max()) if not irr_pct_series.isna().all() else float("nan")
        hm1_range = hm1_max - hm1_min if np.isfinite(hm1_min) and np.isfinite(hm1_max) else float("nan")
        # Show summary stats
        st.markdown("**Heatmap 1 Summary Statistics:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Min IRR", _value_or_placeholder(hm1_min, lambda x: f"{x:.2f}%"))
        with col2:
            st.metric("Max IRR", _value_or_placeholder(hm1_max, lambda x: f"{x:.2f}%"))
        with col3:
            st.metric("Range", _value_or_placeholder(hm1_range, lambda x: f"{x:.2f}%"))

        # Peak cell highlight
        if not df_hm['IRR_pct'].isna().all():
            top = df_hm.loc[df_hm['IRR_pct'].idxmax()]
            st.success(f"Highest mean IRR within this scenario grid: ExitCap {top['ExitCap']} × RentGrowth {top['RentGrowth']} → {top['IRR_pct']:.1f}%")

        # Download button
        st.download_button(
            "Download Heatmap 1 CSV",
            df_hm.to_csv(index=False),
            "heatmap_exit_cap_x_rent_growth.csv",
            "text/csv",
            help="Download the heatmap data as a CSV file for further analysis"
        )

        # Create Altair heatmap only from finite cells to avoid empty-chart warnings.
        df_hm_chart = df_hm.copy()
        df_hm_chart["IRR_pct"] = pd.to_numeric(df_hm_chart["IRR_pct"], errors="coerce")
        df_hm_chart = df_hm_chart[np.isfinite(df_hm_chart["IRR_pct"])]
        if df_hm_chart.empty:
            st.warning("Heatmap 1 ran, but no finite IRR cells were available to chart.")
        else:
            heat = alt.Chart(df_hm_chart).mark_rect().encode(
                x=alt.X("RentGrowth:O", title="Rent Growth (annual)"),
                y=alt.Y("ExitCap:O", title="Exit Cap Rate"),
                color=alt.Color("IRR_pct:Q", title="Mean IRR (%)"),
                tooltip=["ExitCap", "RentGrowth", alt.Tooltip("IRR_pct:Q", format=".1f", title="Mean IRR (%)")],
            )
            labels = alt.Chart(df_hm_chart).mark_text(baseline="middle").encode(
                x="RentGrowth:O", y="ExitCap:O", text=alt.Text("IRR_pct:Q", format=".1f")
            )
            st.altair_chart(
                (heat + labels).properties(width="container", height=380, title="Scenario Sensitivity View: Exit Cap × Rent Growth"),
                use_container_width=True,
            )

        # Show data table
        if SHOW_ADVANCED:
            with st.expander("Heatmap 1 Data Table"):
                st.dataframe(df_hm)
else:
    st.info("Heatmap 1 will appear here after you build it. Click the button above to generate sensitivity analysis.")

    st.markdown("---")

# --- Tornado Sensitivity ---
st.header("Tornado Sensitivity")
_app_log("Entering tornado section")
st.caption("Model-derived bounded sensitivity view. Each bar reruns the current underwriting case with one low/high shock, using the same seed for comparability.")

tornado_col1, tornado_col2, tornado_col3 = st.columns([1, 1, 1])
with tornado_col1:
    st.session_state.tornado_n_per_case = st.number_input(
        "Tornado simulations per case",
        min_value=50,
        max_value=1000,
        value=int(st.session_state.tornado_n_per_case),
        step=50,
        help="Default is 250. Higher values smooth the chart but take longer.",
    )
with tornado_col2:
    st.session_state.tornado_metric = st.selectbox(
        "Tornado metric",
        ["IRR", "NPV", "CoC", "EquityMultiple"],
        index=["IRR", "NPV", "CoC", "EquityMultiple"].index(
            st.session_state.tornado_metric
            if st.session_state.tornado_metric in ["IRR", "NPV", "CoC", "EquityMultiple"]
            else "IRR"
        ),
    )
with tornado_col3:
    st.session_state.tornado_stat = st.selectbox(
        "Tornado statistic",
        ["p50", "mean", "p5", "p95"],
        index=["p50", "mean", "p5", "p95"].index(
            st.session_state.tornado_stat
            if st.session_state.tornado_stat in ["p50", "mean", "p5", "p95"]
            else "p50"
        ),
    )

if st.button("Build Model-Derived Tornado", type="primary", key="model_tornado_btn"):
    _app_log("User clicked Build Model-Derived Tornado")
    try:
        current_params = _current_params_for_engine(seed=int(st.session_state.seed))
        tornado_data = build_tornado_sensitivity_data(
            current_params,
            n_per_case=int(st.session_state.tornado_n_per_case),
            seed=int(st.session_state.seed),
            metric=str(st.session_state.tornado_metric),
            stat=str(st.session_state.tornado_stat),
        )
        st.session_state.tornado_df = tornado_data
        _record_button_audit(
            "Build Model-Derived Tornado",
            tornado_data,
            recompute_tornado_metrics(tornado_data),
        )
        finite_delta = pd.to_numeric(
            tornado_data[["low_delta", "high_delta"]].stack(),
            errors="coerce",
        ).dropna()
        if finite_delta.empty:
            st.warning("Tornado sensitivity ran, but no finite deltas were available for the selected metric.")
        else:
            st.success("Model-derived tornado sensitivity view ready.")
    except Exception as e:
        _app_log(f"Error generating model-derived tornado data: {e}")
        st.session_state.tornado_df = None
        st.error(f"Failed to generate model-derived tornado data: {e}")

df_tornado = st.session_state.get("tornado_df")
if df_tornado is not None and not df_tornado.empty:
    st.markdown("### Model-Derived Tornado Sensitivity Chart")
    chart_df = df_tornado.melt(
        id_vars=["parameter", "low_case", "high_case", "abs_impact"],
        value_vars=["low_delta", "high_delta"],
        var_name="case",
        value_name="delta",
    )
    delta_numeric = pd.to_numeric(chart_df["delta"], errors="coerce")
    chart_df = chart_df[np.isfinite(delta_numeric)]
    if chart_df.empty:
        st.warning("No finite sensitivity deltas are available to chart for the selected metric.")
    else:
        metric = str(st.session_state.tornado_metric)
        axis_format = ".2%" if metric in {"IRR", "CoC"} else ".2s" if metric == "NPV" else ".2f"
        label_format = ".2%" if metric in {"IRR", "CoC"} else ".2s" if metric == "NPV" else ".2f"
        case_labels = {
            "low_delta": "Low shock delta",
            "high_delta": "High shock delta",
        }
        chart_df["case_label"] = chart_df["case"].map(case_labels)
        chart = alt.Chart(chart_df).mark_bar(opacity=0.8).encode(
            x=alt.X("delta:Q", title=f"Delta vs base {metric}", axis=alt.Axis(format=axis_format)),
            y=alt.Y(
                "parameter:N",
                title="Parameter",
                sort=alt.EncodingSortField(field="abs_impact", order="ascending"),
            ),
            color=alt.Color(
                "case_label:N",
                title="Shock",
                scale=alt.Scale(range=["#b45309", "#047857"]),
            ),
            tooltip=[
                "parameter:N",
                "low_case:N",
                "high_case:N",
                alt.Tooltip("delta:Q", format=label_format),
            ],
        ).properties(height=320, title="Model-Derived Tornado Sensitivity")
        st.altair_chart(chart, use_container_width=True)

    display_df = df_tornado[
        ["parameter", "low_case", "high_case", "base_metric", "low_delta", "high_delta", "status"]
    ].copy()
    for col in ["base_metric", "low_delta", "high_delta"]:
        if str(st.session_state.tornado_metric) in {"IRR", "CoC"}:
            display_df[col] = display_df[col].map(lambda x: _fmt_pct(x) if np.isfinite(x) else "—")
        elif str(st.session_state.tornado_metric) == "NPV":
            display_df[col] = display_df[col].map(lambda x: _fmt_money(x) if np.isfinite(x) else "—")
        else:
            display_df[col] = display_df[col].map(lambda x: _fmt_x(x) if np.isfinite(x) else "—")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("Build the model-derived tornado view to compare bounded low/high shocks against the current base case.")

st.markdown("---")
st.subheader("Heatmap 2: Interest Rate × Debt Ratio (LTV) Sensitivity")
st.caption("Scenario sensitivity view aligned to the current underwriting inputs for interest rate and debt ratio.")

sims_per_cell2 = st.slider(
    "Simulations per cell (Heatmap 2)", min_value=100, max_value=2000, value=400, step=100,
    help="More simulations = smoother values but slower computation."
)

# Build button
if st.button("Build Heatmap 2", key="btn_heatmap2"):
    with st.spinner("Computing heatmap 2... This may take a few minutes depending on your simulation count."):
        rate_grid, ltv_grid = _demo_heatmap2_grids()
        st.session_state.hm2_df = _build_heatmap2_cached(
            int(sims_per_cell2),
            int(st.session_state.seed),
            bool(st.session_state.stage2),
            rate_grid=rate_grid,
            ltv_grid=ltv_grid,
            base_rent_psf=float(st.session_state.in_place_rent_psf),
            base_total_rsf=float(st.session_state.total_rsf),
            base_initial_occ=float(st.session_state.initial_occupancy),
            base_market_rent=float(st.session_state.market_rent_psf),
            base_purchase_price=float(st.session_state.purchase_price),
            base_opex_start=float(st.session_state.operating_expenses_start),
            base_opex_growth=float(st.session_state.opex_growth_rate),
            base_tax_rate=float(st.session_state.property_tax_rate),
            base_tax_mode=str(st.session_state.tax_mode),
            base_tax_growth=float(st.session_state.tax_growth_rate),
            base_tax_reassess_on_refi=bool(st.session_state.tax_reassess_on_refi),
            base_tax_reassess_on_sale=bool(st.session_state.tax_reassess_on_sale),
                base_tax_reassess_assessment_ratio=float(st.session_state.tax_reassess_assessment_ratio),
                base_tax_reassess_max_increase_cap_pct=float(st.session_state.tax_reassess_max_increase_cap_pct),
            base_post_refi_io_years=int(st.session_state.post_refi_io_years),
            base_discount_rate=float(st.session_state.discount_rate),
            base_acq_cost_rate=float(st.session_state.acq_cost_rate),
            base_financing_fee_rate=float(st.session_state.financing_fee_rate),
            base_rate_cap_cost=float(st.session_state.rate_cap_cost),
            base_working_capital_reserve=float(st.session_state.working_capital_reserve),
            base_seller_reserve_credit=float(st.session_state.seller_reserve_credit),
            base_contingency_reserve=float(st.session_state.contingency_reserve),
            base_transfer_tax_buy_rate=float(st.session_state.transfer_tax_buy_rate),
            base_transfer_tax_sell_rate=float(st.session_state.transfer_tax_sell_rate),
            base_wc_true_up_close_dollar=float(st.session_state.wc_true_up_close_dollar),
            base_wc_true_up_close_pct_of_opex=float(st.session_state.wc_true_up_close_pct_of_opex),
            base_wc_true_up_sale_dollar=float(st.session_state.wc_true_up_sale_dollar),
            base_wc_true_up_sale_pct_of_opex=float(st.session_state.wc_true_up_sale_pct_of_opex),
            base_capex_schedule=st.session_state.capex_schedule,
            base_sale_cost_rate=float(st.session_state.sale_cost_rate),
            base_price_terminal_with_buyer_tax=bool(st.session_state.price_terminal_with_buyer_tax),
            base_sale_month=_demo_sale_month(),
        )
        _record_button_audit(
            "Build Heatmap 2",
            st.session_state.hm2_df,
            recompute_heatmap_metrics(st.session_state.hm2_df),
            _heatmap_displayed_metrics_for_audit(st.session_state.hm2_df),
        )

# Show heatmap if available
df_hm2 = st.session_state.get("hm2_df")
if df_hm2 is not None and not df_hm2.empty:
    # Validate heatmap data
    if len(df_hm2) > 0 and all(col in df_hm2.columns for col in ['InterestRate', 'DebtRatio', 'IRR_pct']):
        # Make a copy for safe manipulation
        df_hm2 = df_hm2.copy()

        # Metrics
        hm2_irr_series = pd.to_numeric(df_hm2["IRR_pct"], errors="coerce")
        vmin = float(hm2_irr_series.min()) if not hm2_irr_series.isna().all() else float("nan")
        vmax = float(hm2_irr_series.max()) if not hm2_irr_series.isna().all() else float("nan")
        vrange = vmax - vmin if np.isfinite(vmin) and np.isfinite(vmax) else float("nan")

        st.markdown("**Heatmap 2 Summary Statistics:**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Min IRR", _value_or_placeholder(vmin, lambda x: f"{x:.2f}%"))
        c2.metric("Max IRR", _value_or_placeholder(vmax, lambda x: f"{x:.2f}%"))
        c3.metric("Range",  _value_or_placeholder(vrange, lambda x: f"{x:.2f}%"))

        # Sort orders (left→right for rates, bottom→top for LTV)
        rate_order = sorted(df_hm2["InterestRate"].unique(), key=lambda s: float(s.strip("%")))
        ltv_order  = sorted(df_hm2["DebtRatio"].unique(),  key=lambda s: float(s.strip("%")))

        df_hm2_chart = df_hm2.copy()
        df_hm2_chart["IRR_pct"] = pd.to_numeric(df_hm2_chart["IRR_pct"], errors="coerce")
        df_hm2_chart = df_hm2_chart[np.isfinite(df_hm2_chart["IRR_pct"])]
        if df_hm2_chart.empty:
            st.warning("Heatmap 2 ran, but no finite IRR cells were available to chart.")
        else:
            heat = alt.Chart(df_hm2_chart).mark_rect().encode(
                x=alt.X("InterestRate:O", title="Interest Rate", sort=rate_order),
                y=alt.Y("DebtRatio:O",  title="Debt Ratio (LTV)", sort=ltv_order),
                color=alt.Color(
                    "IRR_pct:Q",
                    title="Mean IRR (%)",
                    scale=alt.Scale(domain=[vmin, vmax])
                ),
                tooltip=["InterestRate", "DebtRatio", alt.Tooltip("IRR_pct:Q", title="Mean IRR (%)", format=".1f")],
            )

            labels = alt.Chart(df_hm2_chart).mark_text(baseline="middle").encode(
                x="InterestRate:O", y="DebtRatio:O", text=alt.Text("IRR_pct:Q", format=".1f")
            )

            st.altair_chart(
                (heat + labels).properties(width="container", height=380, title="Scenario Sensitivity View: Interest Rate × Debt Ratio"),
                use_container_width=True,
            )

        # Optional: download CSV
        if SHOW_ADVANCED:
            st.download_button(
                "Download Heatmap 2 CSV",
                data=df_hm2.to_csv(index=False),
                file_name="heatmap_interest_rate_x_debt_ratio.csv",
                mime="text/csv",
                key="dl_hm2",
            )
    else:
        st.warning("Heatmap 2 is preserved and visible, but some grid values are unavailable in the current contract. Please rebuild the grid to refresh the panel.")
else:
    st.info("Heatmap 2 will appear here after you build it. Click the button above to generate sensitivity analysis.")

# Final spacing
st.write("")
st.write("")
st.markdown("---")

# --- AI Analyst Section ---
_render_ai_analyst_chat_section()

st.write("")
st.markdown("---")

# --- Trace / Explain Section ---
st.header("Trace / Explain P50 IRR")
_render_validation_note("info", VALIDATION_COPY["trace"])
trace_df = st.session_state.get("df")
trace_payload = st.session_state.get("trace_payload")
compact_trace_available = isinstance(trace_payload, dict) and bool(trace_payload.get("available"))
if compact_trace_available:
    explain_payload_status = "Selected-run summary available"
    explain_payload_caption = "Engine trace available; full bundle/export flow remains under verification."
elif trace_tools is not None and trace_df is not None and not trace_df.empty:
    explain_payload_status = "Engine trace available"
    explain_payload_caption = "Selected-run trace summary is not currently included in this run."
else:
    explain_payload_status = "Not available"
    explain_payload_caption = "Run the simulation first to enable selected-run trace context."
trace_col1, trace_col2, trace_col3 = st.columns(3)
with trace_col1:
    st.metric("Trace Helper", "Ready" if trace_tools is not None else "Unavailable")
with trace_col2:
    st.metric("Current Run", "Loaded" if trace_df is not None and not trace_df.empty else "Not run")
with trace_col3:
    st.metric("Explain Payload", explain_payload_status)
    st.caption(explain_payload_caption)

if trace_df is None or trace_df.empty:
    st.info("Run the simulation first to enable the preserved Trace / Explain surface.")
else:
    st.caption("Current runtime targets: `equity_cf`, `_ScheduleData`, and `_TerminalData`. Full bundle/export flow remains under verification.")
    with st.expander("Trace surface status", expanded=False):
        st.markdown("""
        - Selected-run replay is supported by `trace_tools.py`.
        - The UI shows compact selected-run status when trace context is available.
        - Full trace bundle export remains under verification.
        - Explainability claims should be limited to runtime signals currently present in the engine contract.
        """)

# --- Exports Section ---
st.markdown("## Exports")
st.markdown("Download simulation results, metrics summary, and input parameters for analysis or sharing.")
st.caption(VALIDATION_COPY["exports"])

# Get the main simulation results DataFrame
df = st.session_state.get("df")

if df is None or df.empty:
    st.info("Run the simulation first to enable exports.")
else:
    st.markdown("### Available Downloads:")

    # Create columns for better layout
    export_col1, export_col2 = st.columns(2)

    with export_col1:
        # 1) Results CSV
        st.download_button(
            "Download results (CSV)",
            data=df.to_csv(index=False),
            file_name="monte_carlo_simulation_results.csv",
            mime="text/csv",
            help="Complete simulation results with all scenarios and metrics"
        )

        # 3) Inputs/overrides JSON
        # Filter session state to only JSON-serializable values
        ss_export = {
            k: v for k, v in st.session_state.items()
            if isinstance(v, (int, float, str, bool, list, dict)) or v is None
        }
        st.download_button(
            "Download inputs / overrides (JSON)",
            data=json.dumps(ss_export, indent=2, default=_json_default),
            file_name="monte_carlo_inputs_overrides.json",
            mime="application/json",
            help="All input parameters and overrides used in this simulation"
        )

    with export_col2:
        # 2) Metrics JSON - Use real calculations from df
        metrics = {}

        # IRR metrics (always available)
        if "IRR" in df.columns:
            irr_series = pd.to_numeric(df["IRR"], errors='coerce').dropna()
            if not irr_series.empty:
                metrics["irr"] = {
                    "mean": float(irr_series.mean()),
                    "median": float(irr_series.median()),
                    "p05": float(irr_series.quantile(0.05)),
                    "p50": float(irr_series.quantile(0.50)),
                    "p95": float(irr_series.quantile(0.95)),
                    "prob_ge_15pct": float((irr_series >= 0.15).mean()),
                    "prob_ge_20pct": float((irr_series >= 0.20).mean())
                }

        # NPV metrics (if available)
        if "NPV" in df.columns:
            npv_series = pd.to_numeric(df["NPV"], errors='coerce').dropna()
            if not npv_series.empty:
                metrics["npv"] = {
                    "mean": float(npv_series.mean()),
                    "median": float(npv_series.median()),
                    "p05": float(npv_series.quantile(0.05)),
                    "p50": float(npv_series.quantile(0.50)),
                    "p95": float(npv_series.quantile(0.95))
                }

        # Equity Multiple metrics (if available)
        if "EquityMultiple" in df.columns:
            em_series = pd.to_numeric(df["EquityMultiple"], errors='coerce').dropna()
            if not em_series.empty:
                metrics["equity_multiple"] = {
                    "mean": float(em_series.mean()),
                    "median": float(em_series.median()),
                    "p05": float(em_series.quantile(0.05)),
                    "p50": float(em_series.quantile(0.50)),
                    "p95": float(em_series.quantile(0.95))
                }

        # Cash-on-Cash metrics (if available)
        if "CoC" in df.columns:
            coc_series = pd.to_numeric(df["CoC"], errors='coerce').dropna()
            if not coc_series.empty:
                metrics["cash_on_cash"] = {
                    "mean": float(coc_series.mean()),
                    "median": float(coc_series.median()),
                    "p05": float(coc_series.quantile(0.05)),
                    "p50": float(coc_series.quantile(0.50)),
                    "p95": float(coc_series.quantile(0.95))
                }

        # Occupancy metrics
        if "PhysicalOccupancyRate" in df.columns:
            po = pd.to_numeric(df["PhysicalOccupancyRate"], errors='coerce').dropna()
            if not po.empty:
                metrics["occupancy_physical"] = {
                    "mean": float(po.mean()),
                    "median": float(po.median()),
                    "p05": float(po.quantile(0.05)),
                    "p50": float(po.quantile(0.50)),
                    "p95": float(po.quantile(0.95))
                }
        if "EconomicOccupancyRate" in df.columns:
            eo = pd.to_numeric(df["EconomicOccupancyRate"], errors='coerce').dropna()
            if not eo.empty:
                metrics["occupancy_economic_contract"] = {
                    "mean": float(eo.mean()),
                    "median": float(eo.median()),
                    "p05": float(eo.quantile(0.05)),
                    "p50": float(eo.quantile(0.50)),
                    "p95": float(eo.quantile(0.95))
                }

        # Add simulation metadata
        metrics["simulation_info"] = {
            "total_scenarios": len(df),
            "columns_count": len(df.columns),
            "export_timestamp": pd.Timestamp.now().isoformat()
        }

        st.download_button(
            "Download metrics (JSON)",
            data=json.dumps(metrics, indent=2, default=_json_default),
            file_name="monte_carlo_metrics_summary.json",
            mime="application/json",
            help="Key performance metrics and statistics from the simulation"
        )

        # 4) ZIP bundle
        try:
            # Create ZIP file in memory
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("monte_carlo_simulation_results.csv", df.to_csv(index=False))
                zf.writestr("monte_carlo_metrics_summary.json", json.dumps(metrics, indent=2, default=_json_default))
                zf.writestr("monte_carlo_inputs_overrides.json", json.dumps(ss_export, indent=2, default=_json_default))

            st.download_button(
                "Download all (ZIP)",
                data=buf.getvalue(),
                file_name="monte_carlo_complete_export.zip",
                mime="application/zip",
                help="Complete export bundle with results, metrics, and inputs"
            )
        except Exception as e:
            st.error(f"Error creating ZIP bundle: {e}")

st.markdown("---")
st.markdown("## Audit Evidence")
st.caption("Local CSV tie-out evidence for banker-style button-press number checks.")
audit_dir = THIS_DIR / "artifacts" / "button_audit"
latest_audit = st.session_state.get("latest_button_audit")
latest_audit_error = st.session_state.get("latest_button_audit_error")

if latest_audit_error:
    st.warning(f"Latest audit logging error: {latest_audit_error}")

if latest_audit:
    ac1, ac2, ac3 = st.columns(3)
    ac1.metric("Latest Audit Run", str(latest_audit.get("run_id", "—"))[-18:])
    ac2.metric("Audit Status", str(latest_audit.get("status", "—")))
    ac3.metric("Failed Tie-Outs", int(latest_audit.get("failed_count", 0)))
    st.caption(f"Full run id: `{latest_audit.get('run_id', '—')}`")
else:
    st.info("Audit evidence will appear after a simulation, heatmap, or tornado button is pressed.")

audit_downloads = [
    ("Download button runs audit CSV", audit_dir / "button_runs.csv", "button_runs.csv"),
    ("Download metric tie-outs CSV", audit_dir / "metric_tieouts.csv", "metric_tieouts.csv"),
]
if latest_audit and latest_audit.get("latest_raw_csv"):
    audit_downloads.append(
        (
            "Download latest raw button output CSV",
            Path(str(latest_audit["latest_raw_csv"])),
            Path(str(latest_audit["latest_raw_csv"])).name,
        )
    )

download_cols = st.columns(min(3, max(1, len(audit_downloads))))
for idx, (label, path, file_name) in enumerate(audit_downloads):
    with download_cols[idx % len(download_cols)]:
        if path.exists():
            st.download_button(
                label,
                data=path.read_bytes(),
                file_name=file_name,
                mime="text/csv",
                key=f"audit_download_{idx}_{file_name}",
            )
        else:
            st.caption(f"{file_name} not created yet.")

st.caption("Monte Carlo Simulation Model — Professional real estate investment analysis with advanced correlation modeling")
