"""
Trace/Explain tools for Monte Carlo real estate model.

This module provides functionality to trace and explain how the model arrives at P50 IRR
by reconstructing the year-by-year schedule and terminal calculations for a specific run.
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional
import rmc_model


def calculate_irr_from_cashflows(cash_flows: list[float]) -> float:
    """Calculate IRR from a list of cash flows using manual calculation."""
    # numpy.irr was deprecated and removed in newer versions
    # Use manual calculation instead
    return _manual_irr_calculation(cash_flows)


def _manual_irr_calculation(cash_flows: list[float], tolerance: float = 1e-6, max_iterations: int = 100) -> float:
    """Manual IRR calculation using Newton-Raphson method."""
    if len(cash_flows) < 2:
        return 0.0
    
    # Initial guess: 10%
    rate = 0.10
    
    for _ in range(max_iterations):
        npv = 0.0
        npv_derivative = 0.0
        
        for i, cf in enumerate(cash_flows):
            if i == 0:
                npv += cf
                npv_derivative += 0  # derivative of constant is 0
            else:
                discount_factor = (1 + rate) ** i
                npv += cf / discount_factor
                npv_derivative += -i * cf / (discount_factor * (1 + rate))
        
        if abs(npv) < tolerance:
            return rate
        
        if abs(npv_derivative) < tolerance:
            break
            
        rate = rate - npv / npv_derivative
        
        # Bounds checking
        if rate < -0.99:
            rate = -0.99
        elif rate > 10.0:
            rate = 10.0
    
    return rate


def find_median_run(df: pd.DataFrame) -> Tuple[int, float]:
    """Find the simulation run index closest to the median IRR."""
    if 'IRR' not in df.columns:
        raise ValueError("DataFrame must contain 'IRR' column")
    
    irr_series = pd.to_numeric(df['IRR'], errors='coerce').dropna()
    if irr_series.empty:
        raise ValueError("No valid IRR values found")
    
    median_irr = irr_series.median()
    
    abs_diff = (irr_series - median_irr).abs()
    min_diff = abs_diff.min()
    ties = abs_diff[abs_diff == min_diff]

    if '_RunIndex' in df.columns:
        tie_rows = df.loc[ties.index].copy()
        tie_rows['_trace_df_index'] = tie_rows.index
        tie_rows['_RunIndex_numeric'] = pd.to_numeric(tie_rows['_RunIndex'], errors='coerce')
        valid_run_idx = tie_rows.dropna(subset=['_RunIndex_numeric'])
        if not valid_run_idx.empty:
            chosen = valid_run_idx.sort_values(['_RunIndex_numeric', '_trace_df_index']).iloc[0]
            return int(chosen['_RunIndex_numeric']), median_irr

    return int(ties.index.min()), median_irr


def _resolve_run_row(df: pd.DataFrame, run_idx: int) -> tuple[pd.Series, int]:
    """Resolve a run identifier to its DataFrame row, preferring _RunIndex when available."""
    if '_RunIndex' in df.columns:
        run_idx_series = pd.to_numeric(df['_RunIndex'], errors='coerce')
        matches = df.loc[run_idx_series == int(run_idx)]
        if not matches.empty:
            row = matches.iloc[0]
            return row, int(matches.index[0])

    if run_idx < 0 or run_idx >= len(df):
        raise ValueError(f"Run index {run_idx} out of range")

    row = df.iloc[run_idx]
    return row, int(run_idx)


def extract_run_identity(df: pd.DataFrame, run_idx: int) -> Dict[str, Any]:
    """Extract run identity information from a specific run."""
    run_row, row_position = _resolve_run_row(df, run_idx)
    
    # Extract seed and run index if available
    identity = {
        "run_index": int(run_row.get('_RunIndex', run_idx)) if pd.notna(run_row.get('_RunIndex', run_idx)) else int(run_idx),
        "row_position": row_position,
        "irr": float(run_row.get('IRR', 0.0)),
        "npv": float(run_row.get('NPV', 0.0)) if 'NPV' in run_row else None,
        "equity_multiple": float(run_row.get('EquityMultiple', 0.0)) if 'EquityMultiple' in run_row else None,
    }
    
    # Look for seed-related columns
    seed_cols = [col for col in df.columns if 'seed' in col.lower() or 'Seed' in col]
    for col in seed_cols:
        identity[col] = run_row.get(col)
    
    return identity


def create_trace_bundle(
    params: Dict[str, Any],
    run_identity: Dict[str, Any],
    mode: str,
    base_seed: int,
    run_idx: int
) -> Dict[str, Any]:
    """Create the complete trace bundle with all required components."""
    
    # 1. Inputs snapshot
    inputs_snapshot = {
        "mode": mode,
        "base_seed": base_seed,
        "run_index": run_idx,
        "derived_seed": _derive_seed_for_run(base_seed, run_idx),
        "parameters": params.copy(),
        "run_identity": run_identity
    }
    
    # 2. Run identity
    run_info = {
        "mode": mode,
        "base_seed": base_seed,
        "run_index": run_idx,
        "derived_seed": _derive_seed_for_run(base_seed, run_idx),
        "irr": run_identity.get("irr"),
        "reproduce_note": f"To reproduce: Set seed={base_seed}, run_index={run_idx}, explain_mode=True"
    }
    
    # 3. Year-by-year schedule (placeholder - will be filled by engine)
    schedule = {
        "years": [],
        "revenue": {},
        "expenses": {},
        "noi": {},
        "leasing_capex": {},
        "debt": {},
        "reserves": {},
        "cash_flows_to_equity": {}
    }
    
    # 4. Terminal calculation block (placeholder - will be filled by engine)
    terminal = {
        "noi_basis": None,
        "exit_cap_rate": None,
        "gross_sale_price": None,
        "sale_costs": {},
        "debt_payoff": None,
        "net_sale_proceeds": None
    }
    
    # 5. IRR proof (placeholder - will be filled by engine)
    irr_proof = {
        "cash_flow_series": [],
        "computed_irr": None,
        "engine_irr": run_identity.get("irr"),
        "consistency_check": {
            "passed": False,
            "difference": None,
            "mismatch_message": None
        }
    }
    
    return {
        "trace_inputs": inputs_snapshot,
        "trace_schedule": schedule,
        "trace_terminal": terminal,
        "trace_cashflows": irr_proof,
        "trace_summary": {
            "irr": run_identity.get("irr"),
            "mode": mode,
            "base_seed": base_seed,
            "run_index": run_idx,
            "reproduce_note": run_info["reproduce_note"]
        }
    }


def validate_irr_consistency(
    cash_flows: list[float],
    engine_irr: float,
    tolerance: float = 1e-6
) -> Dict[str, Any]:
    """Validate that recomputed IRR matches engine IRR within tolerance."""
    computed_irr = calculate_irr_from_cashflows(cash_flows)
    difference = abs(computed_irr - engine_irr)
    
    passed = difference <= tolerance
    
    result = {
        "passed": passed,
        "difference": difference,
        "computed_irr": computed_irr,
        "engine_irr": engine_irr,
        "tolerance": tolerance
    }
    
    if not passed:
        result["mismatch_message"] = f"IRR mismatch: computed={computed_irr:.6f}, engine={engine_irr:.6f}, diff={difference:.6f}"
    
    return result


def export_trace_bundle_to_files(trace_bundle: Dict[str, Any], output_dir: str = ".") -> Dict[str, str]:
    """Export trace bundle components to individual files."""
    import os
    
    file_paths = {}
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Export each component
    for component_name, component_data in trace_bundle.items():
        if component_name == "trace_schedule":
            # Export as both CSV and JSON
            csv_path = os.path.join(output_dir, f"{component_name}.csv")
            json_path = os.path.join(output_dir, f"{component_name}.json")
            
            # CSV export (if schedule data is available)
            if component_data.get("years"):
                schedule_df = pd.DataFrame(component_data)
                schedule_df.to_csv(csv_path, index=False)
                file_paths[f"{component_name}_csv"] = csv_path
            
            # JSON export
            with open(json_path, 'w') as f:
                json.dump(component_data, f, indent=2, default=str)
            file_paths[f"{component_name}_json"] = json_path
            
        else:
            # JSON export for other components
            file_path = os.path.join(output_dir, f"{component_name}.json")
            with open(file_path, 'w') as f:
                json.dump(component_data, f, indent=2, default=str)
            file_paths[component_name] = file_path
    
    return file_paths


def _derive_seed_for_run(base_seed: Optional[int], run_idx: int) -> Optional[int]:
    """Replicate rmc_model.run_simulation seeding: base + i*10007 + 7919."""
    try:
        base = 0 if base_seed is None else int(base_seed)
        i = int(run_idx)
        return int(base + i * 10007 + 7919)
    except Exception:
        return base_seed


def run_trace_simulation(
    params: Dict[str, Any],
    base_seed: int,
    run_idx: int,
    mode: str = "single_run",
    expected_irr: Optional[float] = None,
) -> Dict[str, Any]:
    """Run a trace simulation with explain_mode enabled.

    Uses the same per-run seed derivation as rmc_model.run_simulation so the traced
    run matches the selected run index deterministically.
    """
    
    # Enable explain mode
    trace_params = params.copy()
    trace_params["explain_mode"] = True
    trace_params["debug_return_schedule"] = True
    # Derive the exact per-run seed to faithfully reproduce the selected run
    derived_seed = _derive_seed_for_run(base_seed, run_idx)
    trace_params["_seed"] = derived_seed
    trace_params["_RunIndex"] = run_idx
    
    # Run the model
    try:
        result = rmc_model.run_model(trace_params)
        
        # Extract run identity
        run_identity = {
            "run_index": int(run_idx),
            "irr": result.get("IRR", 0.0),
            "npv": result.get("NPV", 0.0),
            "equity_multiple": result.get("EquityMultiple", 0.0)
        }
        
        # Create trace bundle
        trace_bundle = create_trace_bundle(params, run_identity, mode, base_seed, run_idx)
        trace_bundle['trace_summary']['derived_seed'] = derived_seed
        explain_identity = result.get('_ExplainIdentity')
        if isinstance(explain_identity, dict):
            trace_bundle['trace_summary']['explain_identity'] = explain_identity
            trace_bundle['trace_inputs']['explain_identity'] = explain_identity
        trace_bundle['trace_summary']['replayed_irr'] = run_identity.get('irr')
        if expected_irr is not None:
            replay_diff = abs(float(run_identity['irr']) - float(expected_irr))
            trace_bundle['trace_summary']['selected_irr'] = float(expected_irr)
            trace_bundle['trace_summary']['replay_irr_difference'] = replay_diff
            trace_bundle['trace_summary']['replay_matches_selected'] = replay_diff <= 1e-6
            if replay_diff > 1e-6:
                return {
                    "error": f"Replayed IRR does not match selected run IRR (diff={replay_diff:.8f})",
                    "trace_inputs": trace_bundle["trace_inputs"],
                    "trace_summary": trace_bundle["trace_summary"],
                }
        
        # Extract explain mode data if available
        if result.get('_ExplainMode', False):
            # Update schedule data
            if '_ScheduleData' in result:
                trace_bundle['trace_schedule'] = result['_ScheduleData']
            
            # Update terminal data
            if '_TerminalData' in result:
                trace_bundle['trace_terminal'] = result['_TerminalData']
            
            # Update cash flow data (prefer engine-provided equity_cf) and validate IRR
            cash_flow_series = None
            if '_CashFlowSeries' in result:
                cash_flow_series = result['_CashFlowSeries']
            elif 'equity_cf' in result:
                cash_flow_series = result['equity_cf']

            if isinstance(cash_flow_series, list) and cash_flow_series:
                trace_bundle['trace_cashflows']['cash_flow_series'] = cash_flow_series
                trace_bundle['trace_summary']['cash_flow_count'] = len(cash_flow_series)
                # Validate IRR consistency
                if run_identity.get('irr') is not None:
                    consistency_check = validate_irr_consistency(
                        cash_flow_series,
                        float(run_identity['irr']),
                        tolerance=1e-6
                    )
                    trace_bundle['trace_cashflows']['consistency_check'] = consistency_check
                    trace_bundle['trace_cashflows']['computed_irr'] = consistency_check.get('computed_irr')
        
        return trace_bundle
        
    except Exception as e:
        return {
            "error": str(e),
            "trace_inputs": {
                "mode": mode,
                "base_seed": base_seed,
                "run_index": run_idx,
                "parameters": params.copy()
            }
        }
