# Metrics API Contract

This document defines the canonical structure for metrics returned by all `ui_metrics.py` functions.

## Overview

All metrics functions return **nested dictionaries** with standardized keys and structures, replacing the previous flat key approach. This ensures API consistency and enables proper type checking.

## Standard Structure

### PercentileStats

All metrics follow this standard percentile statistics pattern:

```json
{
  "mean": 0.12,
  "p5": 0.08,
  "p50": 0.11,
  "p95": 0.16
}
```

## Function Contracts

### `irr_stats(df: pd.DataFrame) -> dict`

Returns IRR statistics with probability metrics:

```json
{
  "mean": 0.12,
  "median": 0.115,
  "p5": 0.08,
  "p50": 0.115,
  "p95": 0.16,
  "prob_ge_15": 0.45
}
```

### `return_value_metrics(df: pd.DataFrame) -> dict`

Returns nested return and value metrics:

```json
{
  "coc": {
    "mean": 0.089,
    "p5": 0.065,
    "p50": 0.087,
    "p95": 0.115
  },
  "equity_multiple": {
    "mean": 1.85,
    "p5": 1.45,
    "p50": 1.82,
    "p95": 2.25
  },
  "npv": {
    "mean": 5500000,
    "p5": 2100000,
    "p50": 5200000,
    "p95": 9200000
  },
  "profitability_index": {
    "mean": 1.18,
    "p5": 1.05,
    "p50": 1.16,
    "p95": 1.35
  }
}
```

### `risk_ops_metrics(df: pd.DataFrame) -> dict`

Returns nested risk and operations metrics:

```json
{
  "yoc": {
    "mean": 0.062,
    "p5": 0.055,
    "p50": 0.061,
    "p95": 0.071
  },
  "cap_rate": {
    "mean": 0.058,
    "p5": 0.052,
    "p50": 0.057,
    "p95": 0.065
  },
  "ltv": {
    "mean": 0.68,
    "p5": 0.65,
    "p50": 0.68,
    "p95": 0.72
  },
  "dscr": {
    "mean": 1.42,
    "p5": 1.18,
    "p50": 1.40,
    "p95": 1.68
  },
  "breakeven_occ": {
    "mean": 0.78,
    "p5": 0.72,
    "p50": 0.78,
    "p95": 0.85
  },
  "debt_yield_y1": {
    "mean": 0.095,
    "p5": 0.082,
    "p50": 0.094,
    "p95": 0.109
  }
}

### Occupancy Metrics (engine outputs)

The engine produces two occupancy measures per run, both in decimal form (0.0–1.0):

- PhysicalOccupancyRate: RSF-months basis.
  - Definition: sum(occupied_months × tenant_rsf) / (total_rsf × 12)
  - Counts free months as physically occupied; excludes downtime months.

- EconomicOccupancyRate: cash rent coverage vs contract potential.
  - Definition: cash base rent / scheduled contract rent
  - Uses in-place scheduled rent as the denominator (contracted rate), not market rent.

In UI exports (metrics_summary.json), these appear as nested stats:

```
"occupancy_physical": {
  "mean": 0.87, "median": 0.88, "p05": 0.81, "p50": 0.88, "p95": 0.92
},
"occupancy_economic_contract": {
  "mean": 0.85, "median": 0.85, "p05": 0.78, "p50": 0.85, "p95": 0.90
}
```
```

## End-to-End Example

```python
import ui_metrics

# Run simulation (returns DataFrame)
df = monte_carlo_model.run_simulation(n=1000, seed=42, params=params)

# Get metrics using canonical API
return_metrics = ui_metrics.return_value_metrics(df)
risk_metrics = ui_metrics.risk_ops_metrics(df)
irr_metrics = ui_metrics.irr_stats(df)

# Access nested values safely
def _get(metric_block: dict, name: str, stat: str, default=None):
    try:
        return metric_block.get(name, {}).get(stat, default)
    except Exception:
        return default

# Extract specific values
coc_mean = _get(return_metrics, 'coc', 'mean', 0.0)
coc_p50 = _get(return_metrics, 'coc', 'p50', 0.0)
npv_p95 = _get(return_metrics, 'npv', 'p95', 0.0)

ltv_mean = _get(risk_metrics, 'ltv', 'mean', 0.0)
dscr_p5 = _get(risk_metrics, 'dscr', 'p5', 0.0)

irr_mean = irr_metrics.get('mean', 0.0)
irr_prob_15 = irr_metrics.get('prob_ge_15', 0.0)

# Display in UI
st.metric("Cash-on-Cash (Mean)", f"{coc_mean:.2%}")
st.metric("NPV (P95)", f"${npv_p95:,.0f}")
st.metric("DSCR (P5)", f"{dscr_p5:.2f}×")
```

## Backward Compatibility

### Temporary Flat Key Support

For backward compatibility, flat keys are temporarily supported but emit deprecation warnings:

```python
# ⚠️ DEPRECATED - Will be removed in v1.0.0
coc_mean = return_metrics['coc_mean']  # Emits DeprecationWarning

# ✅ CANONICAL - Use this instead
coc_mean = return_metrics['coc']['mean']
```

### Migration Path

1. **v0.9.0 (Current)**: Both nested and flat keys supported
2. **v1.0.0 (Future)**: Only nested keys supported

**Action Required**: Update all code to use nested structure before v1.0.0.

## Error Handling

All metrics functions handle missing data gracefully:

- Missing columns → `float('nan')` for numeric values
- Empty DataFrames → All metrics return `float('nan')`
- Invalid data → Coerced to numeric or `float('nan')`

## Type Safety

All return structures are defined with TypedDicts in `metrics_schema.py`:

```python
from metrics_schema import ReturnValueTD, RiskOpsTD

def return_value_metrics(df: pd.DataFrame) -> ReturnValueTD:
    # Implementation returns properly typed structure
    pass
```

## Testing

The API contract is validated by:

- **Property tests**: Mathematical invariants (percentile ordering, bounds)
- **Spec tests**: Exact calculations on known data
- **Integration tests**: UI rendering with nested keys
- **Type checking**: MyPy validation of return structures

This ensures the API contract remains stable and reliable across all versions.
