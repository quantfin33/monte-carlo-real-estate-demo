import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy_financial as npf
import sys
import matplotlib as mpl  # type: ignore
import math

# Choose an interactive GUI backend before importing pyplot
try:
    if sys.platform == "darwin":
        mpl.use("MacOSX")
    else:
        mpl.use("TkAgg")
    
except Exception:
    # Fall back silently (e.g., headless env)
    pass

import matplotlib.pyplot as plt  # type: ignore
import seaborn as sns  # type: ignore
import traceback
import os
from matplotlib.colors import TwoSlopeNorm  # type: ignore
import matplotlib.ticker as mticker  # type: ignore
from typing import Optional

# --- Visual style (matplotlib/seaborn polish) ---
sns.set_theme(context="notebook", style="ticks")
plt.rcParams.update({
    'figure.dpi': 120,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'axes.grid': True,
    'grid.alpha': 0.65,
    'grid.linestyle': '--',
})

# === GLOBAL RECOVERY OVERRIDE ===
# If set to 'NNN', 'BASE_YEAR', or 'CAM_CAP', this will override all tenant recovery types.
# Set to None to use individual tenant settings.
#•	NNN = landlord pays nothing (best for landlord). •	BASE_YEAR = landlord pays year 1 baseline forever •	CAM_CAP = landlord pays anything above a set cap. •	None = landlord pays everything (worst for landlord).

GLOBAL_RECOVERY_TYPE = 'NNN'

# === DEBUG MODE ===
# Set to True to enable debug prints in the main loop for NNN recovery tracing
DEBUG_NNN_RECOVERY = False

# === PRESET OVERRIDE ===
# Set to 'market_logical' to auto-apply a few reasonable underwriting toggles.
# Set to None to leave inputs exactly as defined in default_params().
PRESET = None  # options: None, 'market_logical'

# === Visualization constants ===
HEATMAP_RANGE = (0.00, 0.20)  # 0–20% IRR color scale for all heatmaps
TARGET_IRR    = 0.15          # midpoint for diverging colormap (your hurdle)

# === Scenario packs (Base / Downside / Upside) ===
# You can override these in code or via --scenario CLI flag.
SCENARIOS = {
    "Base": {
        # Base uses the model defaults; keep empty or place light tweaks here
    },
    "Downside": {
        # Softer market + tighter debt
        "market_rent_growth_min": 0.00,
        "market_rent_growth_max": 0.02,
        "override_initial_occupancy": 0.80,   # 20% vacancy
        "exit_cap_override": 0.095,
        "interest_rate": 0.075,
        "debt_ratio": 0.40,
    },
    "Upside": {
        # Stronger market + slightly cheaper debt
        "market_rent_growth_min": 0.03,
        "market_rent_growth_max": 0.05,
        "override_initial_occupancy": 0.90,   # 10% vacancy
        "exit_cap_override": 0.080,
        "interest_rate": 0.060,
        "debt_ratio": 0.50,
    },
}

# Default scenario can be set via environment variable SCENARIO (e.g., SCENARIO=Upside)
DEFAULT_SCENARIO = os.environ.get("SCENARIO", "Base")

# Gate the optional covenant smoke tests behind a CLI/env flag

def get_scenario_from_argv(default: str = DEFAULT_SCENARIO):
    """Parse --scenario/-s or --all from CLI; fallback to DEFAULT_SCENARIO."""
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a in ("--scenario", "-s") and i + 1 < len(args):
            return args[i + 1]
        if a in ("--all-scenarios", "--all"):
            return "ALL"
    return default

def validate_correlation_matrix(matrix: list, variables: list) -> tuple[bool, str]:
    """
    Validate correlation matrix for mathematical correctness.
    Returns (is_valid, error_message).
    """
    try:
        # Convert to numpy array
        M = np.array(matrix, dtype=float)
        
        # Check dimensions
        if M.shape != (len(variables), len(variables)):
            return False, f"Matrix shape {M.shape} doesn't match {len(variables)} variables"
        
        # Check symmetry
        if not np.allclose(M, M.T):
            return False, "Matrix is not symmetric"
        
        # Check diagonal elements are 1.0
        if not np.allclose(np.diag(M), 1.0):
            return False, "Diagonal elements must be 1.0"
        
        # Check correlation bounds [-1, 1]
        off_diag = M[~np.eye(M.shape[0], dtype=bool)]
        if np.any(off_diag < -1.0) or np.any(off_diag > 1.0):
            return False, "Off-diagonal elements must be in range [-1, 1]"
        
        # Check positive semi-definiteness via eigenvalues
        eigenvalues = np.linalg.eigvals(M)
        if np.any(eigenvalues < -1e-10):  # Allow small numerical errors
            return False, f"Matrix is not positive semi-definite (eigenvalues: {eigenvalues})"
        
        return True, "Matrix is valid"
        
    except Exception as e:
        return False, f"Validation error: {e}"

def apply_scenario_overrides(base_params: Optional[dict], scenario_name: str) -> dict:
    """Merge SCENARIOS[scenario_name] into base_params dict without mutating inputs."""
    base_params = dict(base_params or {})
    overrides = dict(SCENARIOS.get(scenario_name, {}))
    return {**base_params, **overrides}

def _print_scenario_banner(name: str):
    msg = f"Running scenario: {name}"
    if HAS_RICH and console:
        console.print(Panel(msg, style="magenta"))
    else:
        print("\n" + msg)
        
def _debug_print_scenario(name: str, params: dict):
    """Console helper: show the effective key overrides used for a scenario."""
    keys = [
        "exit_cap_override",
        "interest_rate",
        "debt_ratio",
        "market_rent_growth_min",
        "market_rent_growth_max",
        "override_initial_occupancy",
    ]
    eff = {k: params.get(k, None) for k in keys}
    msg = " | ".join(f"{k}={eff[k]}" for k in keys)
    if HAS_RICH and console:
        console.print(Panel(f"[bold]{name}[/bold] overrides → {msg}", style="blue"))
    else:
        print(f"{name} overrides → {msg}")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

try:
    from rich.console import Console
    from rich.panel import Panel
    HAS_RICH = True
    console = Console()
except Exception:
    HAS_RICH = False
    console = None

try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

try:
    from joblib import Parallel, delayed
    HAS_JOBLIB = True
except Exception:
    HAS_JOBLIB = False


# ============== helpers ==============
def safe_div(a, b):
    """Safe division that handles edge cases and prevents NaN/inf values."""
    if b is None or b == 0 or not np.isfinite(b):
        return np.nan
    if not np.isfinite(a):
        return np.nan
    
    result = a / b
    if not np.isfinite(result):
        return np.nan
    return result

def calculate_irr(cash_flows):
    """Calculate IRR with proper error handling for edge cases."""
    if not cash_flows or len(cash_flows) < 2:
        return np.nan
    
    # Check for all-zero cash flows
    if all(cf == 0 for cf in cash_flows):
        return 0.0
    
    # Check for single-sign cash flows (no IRR possible)
    if all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
        return np.nan
    
    try:
        return npf.irr(cash_flows)
    except Exception:
        # Fallback for numpy_financial failures
        return np.nan

def calculate_npv(discount_rate, cash_flows):
    """
    NPV using the same annual cash-flow timing basis as IRR.
    CF0 occurs at t=0, Year 1 at t=1, Year 2 at t=2, and so on.
    """
    if not cash_flows:
        return 0.0
    
    try:
        n = len(cash_flows)
        cf0 = float(cash_flows[0])
        
        if n == 1:
            return cf0
        
        # Validate discount rate
        if not np.isfinite(discount_rate) or discount_rate <= -1:
            return np.nan
            
        return cf0 + sum(
            float(cf) / ((1.0 + float(discount_rate)) ** t)
            for t, cf in enumerate(cash_flows[1:], start=1)
        )
    except Exception:
        return np.nan

def _nanmin_finite(xs):
    a = np.array(xs, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.min()) if a.size else np.nan

# ============== smoke config (aggregated warnings) ==============
SMOKE_MODE = os.environ.get("SMOKE_MODE", "aggregate").lower()  # 'aggregate' | 'print' | 'off'
SMOKE_SAMPLE_LIMIT = int(os.environ.get("SMOKE_SAMPLE_LIMIT", "3"))
_SMOKE_BUFFER = {}  # event -> {"count": int, "examples": [dict]}

def _format_vals(vals: dict) -> str:
    parts = []
    for k, v in vals.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            try:
                parts.append(f"{k}={v:.4f}")
            except Exception:
                parts.append(f"{k}={v}")
        else:
            parts.append(f"{k}={v}")
    return " | ".join(parts)


def _smoke_reset():
    """Clear the aggregated warning buffer before a simulation run."""
    _SMOKE_BUFFER.clear()


def _smoke_flush(context: Optional[str] = None):
    """Print one summary line per simulation. Always prints, even if no warnings."""
    header = f"Warnings{(' — ' + context) if context else ''}: "

    if not _SMOKE_BUFFER:
        out = header + "none"
        try:
            if HAS_RICH and console:
                console.print(out)
            else:
                print(out)
        except Exception:
            print(out)
        return

    lines = []
    for evt, rec in sorted(_SMOKE_BUFFER.items()):
        example = ""
        if rec.get("examples"):
            example = f" (e.g., {_format_vals(rec['examples'][0])})"
        lines.append(f"{evt}: {rec.get('count', 0)} hits{example}")

    out = header + "; ".join(lines)
    try:
        if HAS_RICH and console:
            console.print(out)
        else:
            print(out)
    except Exception:
        print(out)

# ============== smoke alarm helper ==============
def _smoke(event, **vals):
    """
    Lightweight warning hook.
    Default (SMOKE_MODE='aggregate'): buffer all events and print once per run via _smoke_flush().
    Set SMOKE_MODE='print' to emit each event immediately.
    Set SMOKE_MODE='off' to silence.
    """
    mode = SMOKE_MODE
    if mode == 'off':
        return
    evt = str(event).upper()

    if mode == 'print':
        # Old behavior, but without red styling
        msg = f"[WARN] {evt} — " + _format_vals(vals)
        try:
            if HAS_RICH and console:
                console.print(msg)
            else:
                print(msg)
        except Exception:
            print(msg)
        return

    # Aggregate mode: count and keep up to SMOKE_SAMPLE_LIMIT examples per event
    rec = _SMOKE_BUFFER.setdefault(evt, {'count': 0, 'examples': []})
    rec['count'] += 1
    if len(rec['examples']) < SMOKE_SAMPLE_LIMIT:
        rec['examples'].append(vals.copy())


def _pv_defeasance(principal, note_rate, amort_payment, years_remaining, io_years_remaining,
                   df_method='flat', rf_flat=0.045, rf_curve=None):
    """
    Present value of the remaining loan payment stream discounted at risk-free rates.
    Annual cadence:
      - First `io_years_remaining` years: interest-only = principal * note_rate
      - Thereafter: level amortization with payment = `amort_payment`
    Discounting:
      - 'flat' uses rf_flat for all years
      - 'curve' uses rf_curve.get(k, rf_flat) for year k (1..N)
    """
    # Input validation
    if not np.isfinite(principal) or principal <= 0:
        return 0.0
    if not np.isfinite(note_rate) or note_rate < 0:
        return 0.0
    if not np.isfinite(amort_payment) or amort_payment < 0:
        return 0.0
    if not np.isfinite(years_remaining) or years_remaining <= 0:
        return 0.0
    if not np.isfinite(io_years_remaining) or io_years_remaining < 0:
        return 0.0
    if not np.isfinite(rf_flat) or rf_flat < -1:
        return 0.0
    
    pv = 0.0
    bal = float(principal)
    rf_curve = rf_curve or {}
    
    try:
        for k in range(1, int(max(years_remaining, 0)) + 1):
            rf = float(rf_flat) if df_method == 'flat' else float(rf_curve.get(k, rf_flat))
            if not np.isfinite(rf) or rf < -1:
                rf = rf_flat  # fallback to flat rate
            
            df = 1.0 / ((1 + rf) ** k)
            if not np.isfinite(df):
                continue

            if k <= max(int(io_years_remaining), 0):
                pay = bal * float(note_rate)  # interest-only
            else:
                pay = float(amort_payment) if amort_payment > 0 else bal * float(note_rate)
                interest = bal * float(note_rate)
                principal_pay = max(pay - interest, 0.0)
                bal = max(bal - principal_pay, 0.0)

            if np.isfinite(pay) and np.isfinite(df):
                pv += pay * df
    except Exception:
        return 0.0

    return pv if np.isfinite(pv) else 0.0


# --- Stepdown rate lookup helper ---
def _lookup_stepdown_rate(stepdown, year):
    """Return the stepdown rate for a given year.
    Rules:
      - Exact match uses that year's rate.
      - Otherwise, use the closest bucket at or before `year` (floor).
      - If `year` is earlier than any key, use the earliest key's rate (extrapolate).
    """
    if not stepdown or not isinstance(stepdown, dict):
        return 0.0
    
    # Validate year input
    if not isinstance(year, (int, float)) or not np.isfinite(year) or year < 0:
        return 0.0
    
    # Normalize keys to ints in case they come as strings
    try:
        keys_sorted = sorted(int(k) for k in stepdown.keys() if isinstance(k, (int, float, str)))
        if not keys_sorted:
            return 0.0
    except Exception:
        return 0.0
    
    # Direct hit
    if year in stepdown:
        try:
            rate = float(stepdown[year])
            return rate if np.isfinite(rate) else 0.0
        except Exception:
            return 0.0
    
    # Floor to the last key <= year, else earliest key
    le_keys = [k for k in keys_sorted if k <= year]
    if le_keys:
        k = le_keys[-1]
    else:
        k = keys_sorted[0]
    
    try:
        rate = float(stepdown.get(k, stepdown.get(str(k), 0.0)))
        return rate if np.isfinite(rate) else 0.0
    except Exception:
        return 0.0

def default_params():
    # Define building-wide scalars once so other fields can reference them
    total_rsf = 630_594          # total rentable SF for the property
    initial_occupancy = 0.826    # 82.6% leased at acquisition 
    walt_years = 7.0             # Weighted Average Lease Term in YEARS used to seed tenant `term_years` in lease_roll. Increase to push expiries out; decrease to make leases roll sooner. Sets initial terms only—does not force renewals.
    in_place_rent_psf = 23.64    # Current average CONTRACTED base rent ($/RSF/YR) for occupied space. Feeds Year‑1 scheduled rent & breakeven. Update from the client's rent roll; keep separate from market assumptions.
    market_rent_psf_var = 27.0   # Today's MARKET rent "top‑of‑house" ($/RSF/YR) used for mark‑to‑market on new/renewals; it then grows each year by market_rent_growth_min/max. Raise for stronger market; lower to be conservative.

    # NOTE: GLOBAL_RECOVERY_TYPE can force all tenants to use the same recovery type for testing or scenario analysis.
    return dict(
        purchase_price=130_000_000,  # initial purchase price
        operating_expenses_start=3_200_000,  # initial annual operating expenses
        opex_growth_rate=0.035,         # Annual % increase for OPERATING EXPENSES after Year 1. 0.035 = 3.5%. Typical range 2–4%. Drives opex growth each year.
        property_tax_rate=0.015,         # The percentage of a property's value that must be paid each year as tax 
        tax_mode='independent',        # How assessed value grows: 'rent_indexed' = follows market_rent/value_index; 'independent' = grows at tax_growth_rate regardless of rents.
        tax_growth_rate=0.025,          # Used ONLY when tax_mode='independent'. Annual % growth of assessed value; 0.025 = 2.5%. If you mistakenly enter 2.5, the model auto-interprets as 2.5%.
        # Tax reassessment controls (default: only on refi, applied next year; no cap/phase‑in)
        tax_reassessment={
            'on_refi': True,                 # If you refinance, the system resets your taxable value to the new appraised value.
            'on_sale': True,                #  If you sell, taxes reset for the buyer at the new appraised value.
            'assessment_ratio': 1.00,        # This is "how much of the market value gets taxed."
            'phase_in_years': 3,             #	Instead of hitting you with the full increase at once (ouch), you tell the system: "Spread that pain over N years."
            'max_increase_cap_pct': 0.1,    # "Never increase my taxes by more than X% in a single year."
            'effective_same_year_refi': False, #After a refi, don't raise taxes in that same year wait until the next year.
            'effective_same_year_sale': True, #  After a sale, raise taxes immediately that same year.
        },
        vacancy_auto_lease=True,       # Vacancy behavior: True = the 'Vacant' bucket leases like others via lease_roll; False = treat as persistent vacancy (no rent/recoveries) until explicitly changed.

        in_place_rent_psf=in_place_rent_psf,  # In-place CONTRACTED base rent ($/RSF/YR). Used for Year‑1 scheduled rent & breakeven; separate from market_rent_psf used for mark‑to‑market.

        # opex structure / CAM logic
        controllable_opex_pct=0.70,   # tenant pays the rest of the 1-opex =x% + the cap if there was an increase ... while the landlord pays the opex controllable % + anything above % cap
        default_controllable_cap_pct=0.05,  # Lower = more tenant‑friendly; higher = more landlord‑friendly.

        # leverage
        debt_ratio=0.50,          # % of total_cost financed by debt (Loan‑to‑Value). 0.30 = 30% LTV. Drives loan_amount, interest cost, DSCR/LTV metrics.
        interest_rate=0.0725,     # Annual note rate on the debt. 0.0725 = 7.25% (simple annual). Applied to current principal balance each year.

        # refinance (0 disables)
        refi_year=5,              # Attempt a refinance in model Year N (Year 1 = first modeled year). Set to 0 to fully disable refi logic.
        refi_cost_rate=0.025,     # Refi transaction costs as a % of the NEW loan (e.g., 0.025 = 2.5%). Deducted from any refi cash‑out.

        # debt structure
        interest_only_years=2,    # Number of initial years with interest‑only payments (no scheduled principal). After this, amortization begins unless refi resets IO.
        amort_years=25,           # Amortization term in YEARS used to compute the level payment when not in IO (e.g., 25‑year amort schedule).
        post_refi_io_years=1,     # Interest‑only period AFTER a successful refi (years). 0 = none. Only takes effect if the refi actually happens.

        # valuation / NPV
        discount_rate=0.105,      # interest rate you use to convert future cash flows into today's value. more=worth less today; less=worth more today.

        # acquisition/financing/reserves/capex/exit costs
        acq_cost_rate=0.015,#Extra transaction costs when buying the property (legal fees, due diligence, closing costs).
        financing_fee_rate=0.01, #Upfront lender fees for arranging the loan .
        rate_cap_cost=0.015,  #Cost of buying an interest rate cap (insurance against floating rates rising too high).
        working_capital_reserve=1_000_000,#Cash set aside at closing to cover day-to-day shortfalls (like rent-up delays, expenses).
        seller_reserve_credit=0, #	If the seller left behind any reserves (like prepaid taxes or deposits)
        contingency_reserve= 1_500_000, #Extra pot of money held back for unexpected costs (repairs, overruns, surprises).
        
        # --- Transfer taxes (enable by setting a non-zero rate) ---
        transfer_tax_buy_rate=0.015,   # A tax charged when you buy the property.
        transfer_tax_sell_rate=0.01,  # A tax charged when you sell the property.
        
        # --- Working capital true-up (flexible; all defaults OFF) ---
        wc_true_up_close_dollar=250_000,         #Extra cash you set aside at closing so the property has money to run smoothly.: Increases the equity needed at purchase (higher upfront cost).
        wc_true_up_close_pct_of_opex=0.055,      # % of first-year opex (annualized) applied at closing 
        wc_true_up_sale_dollar=150_000,          # "You kept reserves for operations; pass them to me."
        wc_true_up_sale_pct_of_opex=0.025,     # Alternative way to size that refund
        capex_schedule={1:500_000, 2: 300_000 ,3: 200_000},
        sale_cost_rate=0.02,#Your sale proceeds drop 
        # Price exit using buyer's first-year tax after reassessment (algebraic, no iteration)
        price_terminal_with_buyer_tax=True,  # "Should the sale price calculation reflect that buyers care about all-in yield after property tax?" (it affects the sale pricea a lot)
        # Optional sale timing within the sale year (1-12). None = full-year.
        sale_month=None,
        
        # --- Exit Cap Rate Sampling Parameters ---
        exit_cap_left=0.085,      # Left bound of triangular distribution for random sampling
        exit_cap_mode=0.090,      # Mode (peak) of triangular distribution for random sampling
        exit_cap_right=0.0975,    # Right bound of triangular distribution for random sampling

        # --- Debt / covenant / refi controls (all default OFF; no economics change unless toggled) ---
        amortization_granularity='monthly',   # 'annual' (default, current behavior) or 'monthly' (record-only; totals unchanged)
        covenant_track=True,                # track DSCR/DY/LTV each year (warn only)
        covenant_thresholds={'dscr_min':1.25,'dy_min':0.08,'ltv_max':0.65},
        covenant_action='Warn',              # 'warn' or 'flag' (no cash impact)
        refi_boxes={'enabled':True ,'lockout_years':0,'max_ltv':0.65,'min_dscr':1.30,'min_dy':0.08},
        prepay={
    'model':'defeasance',        # options: 'none','stepdown','ym','defeasance'
    'lockout_years':0,
    'stepdown':{1:0.05,2:0.04,3:0.03,4:0.02,5:0.01},
    'ym_spread':0.02,          # yield-maintenance proxy spread
    # --- defeasance controls (used only when model='defeasance') ---
    'defeasance_open_year': None,  # if set, stop stream at this year (e.g., last open period). None = to maturity
    'df_method':'flat',            # 'flat' = use rf_flat_rate; 'curve' = use rf_curve per year
    'rf_flat_rate':0.045,          # flat risk-free rate for discounting (e.g., 4.5%)
    'rf_curve':{1:0.043, 2:0.044, 3:0.05},                 # {1:0.043,2:0.044,...} optional per-year risk-free curve
    'fees_bps':30                  # admin/legal/servicer fees in bps of PV (e.g., 30 = 0.30%)
    },  # simple placeholders
                prepay_at_sale=True,        # if True, apply prepayment penalty at sale using the same prepay model
        debug_return_schedule=True ,         # if True, include full debt schedule in results (for debugging)

        # --- Capex buckets / reserves (defaults keep behavior unchanged) ---
        reserve_per_rsf=0.25,          # annual replacement reserve accrual per RSF (cash outflow below NOI)
        reserve_start_year=1,         # first year to start accruing reserves
        reserve_escalation=0.03,       # annual escalation of reserve per RSF
        reserve_policy='offset_building', # 'accrue_only' or 'offset_building' (use reserves to fund building capex)

        # --- Lease roll (tenant schedule) ---
        total_rsf=total_rsf,           # building size (RSF) – single source of truth
        market_rent_psf=market_rent_psf_var,  # $/RSF/yr NNN (from memo; will grow)
        # lease_roll will be dynamically constructed by _reconstruct_lease_roll()
        market_rent_growth_min=0.01,   # annual market rent growth lower bound (shuffles each year)
        market_rent_growth_max=0.025,  # annual market rent growth upper bound (shuffles each year)
        rent_spread_std=0.05,        # random spread applied to mark-to-market on new deals
        renewal_spread_std=0.01,     # random spread applied on renewals vs market

        # reported WALT (years) – static input from memo
        walt_years=walt_years,

        # expose initial occupancy so callers/tests can override dynamically
        initial_occupancy=initial_occupancy,

        # --- Latent market strength (OFF by default) ---
        # If enabled, each run draws a latent factor that simultaneously:
        #   • sets an implied initial occupancy via override_initial_occupancy
        #   • tilts the per‑year rent‑growth band (min/max) up or down
        # Correlate the two shocks at ρ = −0.6 so weaker markets (higher vacancy)
        # coincide with lower rent growth. This block only declares defaults; logic
        # that uses it will be added separately.
        latent_market={
            'enabled': False,          # keep OFF by default (no behavior change)
            'rho': -0.6,               # corr(occupancy_shock, growth_tilt) target
            # Occupancy shock parameters
            'occ_mean': initial_occupancy,  # baseline if enabled
            'occ_sigma': 0.08,         # stdev for occupancy shock (absolute, not % points)
            'occ_clamp': (0.50, 0.98), # clamp resulting occupancy into a sane band
            # Growth tilt parameters
            # Interpreted as a symmetric tilt in percentage points applied to the
            # per‑year uniform growth band (min/max). E.g., tilt_pp=0.01 allows up to
            # ±100 bps shift per year when the latent factor is at ±1σ.
            'tilt_pp': 0.01,           # 100 bps = 0.01
            # Randomness isolation (optional): add to base seed if you want this
            # latent draw to be independent from other model randomness.
            'seed_offset': 0
        }
        ,
        # --- Generalized correlation engine (Stage 2) ---
        # Optional k-variable correlation matrix. When enabled, draws standard normals
        # with Cholesky and maps each to a target variable:
        #   • 'occ0'     → initial occupancy override (same mapping as latent_market)
        #   • 'rg_bias'  → rent-growth tilt (adds to growth band each year)
        #   • 'exit_cap_q' → exit-cap quantile (passed to inverse-CDF of triangular)
        #   • 'rate_q'   → interest-rate quantile (mapped to a band if provided)
        # If disabled, model behaves identically to before.
         correlations={
            'enabled': False,
            'variables': ['occ0', 'rg_bias'],  # minimal default (matches Stage 1 behavior)
            'matrix': [
                [ 1.0, -0.6],
                [-0.6,  1.0]
            ],
            # Optional mapping helpers (only used if present):
            # For interest rate mapping from a quantile in [0,1]; if None, note rate stays unchanged.
            'rate_band': None,   # e.g., (0.055, 0.085)
            # Optional seed offset for correlation draw (isolates randomness if desired)
            'seed_offset': 0
        }
    )
# ============== preset helper ==============
def apply_preset(p):
    """
    Optionally auto-tweak a few inputs to look 'standard-market logical'.
    Toggle with PRESET at the top of the file.
    """
    if PRESET == 'market_logical':
        # 1) Treat 'Vacant' as true vacancy
        p['vacancy_auto_lease'] = False
        # 2) Make taxes independent of rent growth at ~2.5%/yr
        p['tax_mode'] = 'independent'
        p['tax_growth_rate'] = 0.025
        # 3) Raise leverage into a more typical underwriting band (mid-50s)
        p['debt_ratio'] = 0.55
        # (You can extend this with more tweaks later if desired.)
    return p

# ============== sampling ==============

def sample_exit_cap_rate(left=0.075, mode=0.085, right=0.09):   # configurable per run
    """
    Sample exit cap rate from triangular distribution.
    Default values match the original hardcoded parameters.
    Parameters can be overridden via UI session state.
    """
    # Ensure parameters are valid for triangular distribution
    left = max(0.01, min(0.20, float(left)))
    mode = max(0.01, min(0.20, float(mode)))
    right = max(0.01, min(0.20, float(right)))
    
    # Enforce triangular distribution constraints
    if left > mode:
        left, mode = mode, left
    if mode > right:
        mode, right = right, mode
    if left > right:
        left, right = right, left
    
    return np.random.triangular(left=left, mode=mode, right=right)

def _std_norm_cdf(x):
    """Map a standard normal to uniform via Φ(x) with safety checks."""
    try:
        if not np.isfinite(x):
            return 0.5  # return 0.5 for non-finite inputs
        
        result = 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))
        
        # Ensure result is in valid range [0, 1]
        if np.isfinite(result):
            return max(0.0, min(1.0, result))
        else:
            return 0.5  # return 0.5 for non-finite results
    except Exception:
        return 0.5  # return 0.5 as fallback

def sample_exit_cap_rate_from_quantile(u):
    """
    Inverse CDF of the triangular(left=0.075, mode=0.085, right=0.09).
    u should be in [0,1]. Returns the corresponding exit cap.
    """
    # Input validation
    if not np.isfinite(u) or u < 0 or u > 1:
        return 0.085  # return mode as fallback
    
    try:
        a, c, b = 0.075, 0.085, 0.090
        u = min(max(float(u), 0.0), 1.0)
        fc = (c - a) / (b - a)
        if u <= fc:
            result = a + math.sqrt(u * (b - a) * (c - a))
        else:
            result = b - math.sqrt((1.0 - u) * (b - a) * (b - c))
        
        # Ensure result is finite and in valid range
        if np.isfinite(result) and a <= result <= b:
            return result
        else:
            return c  # return mode as fallback
    except Exception:
        return 0.085  # return mode as fallback

def sample_cost_overrun():    # fixed per run
    return np.random.normal(loc=0.03, scale=0.03)

def sample_sale_year():       # fixed per run
    return np.random.choice([6, 7])

# ============== lease roll helpers ==============

def _reconstruct_lease_roll(p):
    """
    Dynamically reconstruct lease_roll based on current parameters.
    This ensures that changes to walt_years, initial_occupancy, etc. are reflected.
    """
    # Get current parameters
    total_rsf = float(p.get('total_rsf', 630594))
    initial_occupancy = float(p.get('initial_occupancy', 0.826))
    walt_years = float(p.get('walt_years', 7.0))
    in_place_rent_psf = float(p.get('in_place_rent_psf', 23.64))
    renew_prob = float(p.get('renew_prob', 0.60))
    
    # Reconstruct lease_roll with current parameters
    lease_roll = [
        {
            'name': 'Top10+Rest',
            'rsf': initial_occupancy * total_rsf,
            'term_years': walt_years,  # Use current walt_years
            'rent_psf': in_place_rent_psf,
            'free_months': 0,
            'ti_psf_new': 60.0,
            'ti_psf_renew': 25.0,
            'lc_pct_new': 0.06,
            'lc_pct_renew': 0.06,
            'renew_prob': renew_prob,
            'downtime_months': 6,
            'recovery_type': GLOBAL_RECOVERY_TYPE if GLOBAL_RECOVERY_TYPE is not None else 'NNN',
            'controllable_cap_pct': 0.05,
        },
        {
            'name': 'Vacant',
            'is_vacancy_bucket': True,
            'rsf': (1 - initial_occupancy) * total_rsf,
            'term_years': 6,
            'rent_psf': 23,  # placeholder for vacancy
            'free_months': 0,
            'ti_psf_new': 40.0,
            'ti_psf_renew': 23.0,
            'lc_pct_new': 0.06,
            'lc_pct_renew': 0.06,
            'renew_prob': renew_prob,
            'downtime_months': 3,
            'recovery_type': GLOBAL_RECOVERY_TYPE if GLOBAL_RECOVERY_TYPE is not None else 'NNN',
            'controllable_cap_pct': 0.05,
        },
    ]
    
    return lease_roll

def _init_lease_state(p):
    """Creates a per-tenant mutable state list from params['lease_roll']."""
    state = []
    
    # Validate lease_roll input
    if not isinstance(p.get('lease_roll'), list):
        return state
    
    for t in p['lease_roll']:
        if not isinstance(t, dict):
            continue
            
        # copy and add runtime fields
        item = dict(t)
        
        # Safe conversion of numeric fields
        try:
            item['remaining_free_months'] = max(int(item.get('free_months', 0)), 0)
            item['term_months'] = int(round(item.get('term_years', 0) * 12))
            item['months_until_expiry'] = item['term_months']
        except (ValueError, TypeError):
            item['remaining_free_months'] = 0
            item['term_months'] = 0
            item['months_until_expiry'] = 0
        
        # runtime fields for recoveries logic
        item['occupied_months_this_year'] = 0
        item['base_year_total_opex'] = None
        item['base_year_controllable_opex'] = None
        item['base_year_set_year'] = None
        item['reset_base_year_now'] = False
        
        # Safe pro-rata share calculation
        try:
            total_rsf = float(p.get('total_rsf', 0.0))
            rsf = float(item.get('rsf', 0.0))
            if total_rsf > 0 and np.isfinite(total_rsf) and np.isfinite(rsf):
                item['pro_rata_share'] = rsf / total_rsf
            else:
                item['pro_rata_share'] = 0.0
        except (ValueError, TypeError, ZeroDivisionError):
            item['pro_rata_share'] = 0.0
            
        state.append(item)
    return state


def _advance_one_year_lease_roll(p, lease_state, market_rent_psf, rng, months=12, collect_stats=False):
    """
    Steps the lease roll forward one year (12 months), returns:
      cash_rent, ti_spend, lc_spend, ending_vacant_rsf, updated_state
    Includes: free rent burn-off, expiries with renewal probability, downtime, mark-to-market.
    """
    cash_rent = 0.0
    scheduled_contract_rent = 0.0
    occupied_rsf_months = 0.0
    renewal_events = 0
    lease_events = 0
    ti_spend = 0.0
    lc_spend = 0.0
    ending_vacant = 0.0

    for item in lease_state:
        rsf = item['rsf']
        item['occupied_months_this_year'] = 0
        if rsf <= 0:
            ending_vacant += 0
            continue
        # Treat designated vacancy bucket as true vacancy only if vacancy_auto_lease=False
        if item.get('is_vacancy_bucket', False) and not p.get('vacancy_auto_lease', True):
            ending_vacant += rsf
            continue

        # month-by-month inside the year (simple loop keeps logic readable)
        m = 0
        while m < months:
            if item['months_until_expiry'] == 0:
                # handle expiry: renew vs new lease
                renew = rng.random() < item.get('renew_prob', 0.5)
                lease_events += 1
                if renew:
                    renewal_events += 1
                # mark-to-market base rent
                if renew:
                    new_rent = market_rent_psf * (1 + rng.normal(0, p.get('renewal_spread_std', 0.01)))
                    ti = rsf * item.get('ti_psf_renew', 0.0)
                    lc_rate = item.get('lc_pct_renew', 0.0)
                    # renewal assumed no downtime, minimal free rent; use same term
                    free_mo = max(int(item.get('free_months', 0) // 2), 0)
                    downtime = 0
                else:
                    new_rent = market_rent_psf * (1 + rng.normal(0, p.get('rent_spread_std', 0.02)))
                    ti = rsf * item.get('ti_psf_new', 0.0)
                    lc_rate = item.get('lc_pct_new', 0.0)
                    free_mo = max(int(item.get('free_months', 0)), 0)
                    downtime = max(int(item.get('downtime_months', 0)), 0)

                # LC based on first year total rent (very common simplification)
                lc = lc_rate * (new_rent * rsf)
                ti_spend += ti
                lc_spend += lc

                # reset lease terms
                item['rent_psf'] = new_rent
                item['remaining_free_months'] = free_mo
                item['months_until_expiry'] = max(int(round(item.get('term_years', 0) * 12)), 12)
                # reset base year on any new term (renewal or new lease)
                item['reset_base_year_now'] = True

                # apply downtime by skipping rent accrual for these months
                skip = min(downtime, months - m)
                m += skip
                if m >= months:
                    break

            # accrue one month of rent (unless in free month)
            scheduled_contract_rent += (item['rent_psf'] * rsf) / 12.0
            if item['remaining_free_months'] > 0:
                item['remaining_free_months'] -= 1
            else:
                cash_rent += (item['rent_psf'] * rsf) / 12.0
            # count as occupied even during free months; downtime months are skipped above
            item['occupied_months_this_year'] += 1
            occupied_rsf_months += rsf

            # advance one month toward expiry
            if item['months_until_expiry'] > 0:
                item['months_until_expiry'] -= 1
            m += 1

        # track vacancy for report (months-end view; simplistic – counts any zero-rent as occupied once free rent is over)
        if item['rent_psf'] <= 0:
            ending_vacant += rsf

    if collect_stats:
        return (
            cash_rent,
            scheduled_contract_rent,
            occupied_rsf_months,
            renewal_events,
            lease_events,
            ti_spend,
            lc_spend,
            ending_vacant,
            lease_state,
        )

    return cash_rent, ti_spend, lc_spend, ending_vacant, lease_state


# ========== Recovery helper ==========
def _compute_recoveries(p, lease_state, controllable_opex, noncontrollable_opex, property_tax, current_year, months_in_year=12):
    """Return total recoveries for the year based on tenant recovery_type.
    Rules:
      - NNN: pro-rata share of (total opex + property tax) scaled by occupancy-months.
      - BASE_YEAR: share of (current total opex - base-year total opex), floored at 0, scaled by occupancy.
      - CAM_CAP: full non-controllable pass-through + controllable increase above a NON-COMPOUNDING cap.
    """
    
    # Input validation
    if not isinstance(lease_state, list) or not lease_state:
        return 0.0
    
    if not np.isfinite(controllable_opex) or not np.isfinite(noncontrollable_opex) or not np.isfinite(property_tax):
        return 0.0
    
    total_opex = controllable_opex + noncontrollable_opex
    default_cap = p.get('default_controllable_cap_pct', 0.05)
    total = 0.0
    
    for item in lease_state:
        if not isinstance(item, dict):
            continue
            
        rsf = item.get('rsf', 0.0)
        if rsf <= 0 or not np.isfinite(rsf):
            continue
            
        # Safe occupancy fraction calculation
        try:
            occ_months = item.get('occupied_months_this_year', 0)
            if not isinstance(occ_months, (int, float)) or not np.isfinite(occ_months):
                occ_months = 0
            occ_frac = min(max(occ_months / float(max(months_in_year, 1)), 0.0), 1.0)
        except (ValueError, TypeError, ZeroDivisionError):
            occ_frac = 0.0
            
        share = item.get('pro_rata_share', 0.0)
        if occ_frac <= 0 or share <= 0 or not np.isfinite(share):
            continue

        rtype = str(item.get('recovery_type', 'NNN')).upper()
        recov = 0.0
        
        try:
            if rtype == 'NNN':
                recov = share * (total_opex + property_tax) * occ_frac
            elif rtype == 'BASE_YEAR':
                base_total = item.get('base_year_total_opex')
                if base_total is None or not np.isfinite(base_total):
                    base_total = total_opex  # defensive default
                # Note: base_total should be full year, so we need to annualize current year's total_opex for comparison
                total_opex_full_year = total_opex / (months_in_year / 12.0) if months_in_year != 12 else total_opex
                delta = max(total_opex_full_year - base_total, 0.0)
                # Convert back to fractional for the recovery calculation
                delta_fractional = delta * (months_in_year / 12.0)
                recov = share * delta_fractional * occ_frac
            elif rtype == 'CAM_CAP':
                cap_pct = item.get('controllable_cap_pct', default_cap)
                if not np.isfinite(cap_pct) or cap_pct < 0:
                    cap_pct = default_cap
                    
                base_cont = item.get('base_year_controllable_opex')
                if base_cont is None or not np.isfinite(base_cont):
                    base_cont = controllable_opex  # defensive default
                    
                # Non-compounding cap: ceiling stays base_cont * (1 + cap_pct)
                # Note: base_cont should be full year, so we need to annualize current year's controllable_opex for comparison
                cap_ceiling = base_cont * (1 + cap_pct)
                
                # Convert fractional controllable_opex back to full year for comparison
                controllable_opex_full_year = controllable_opex / (months_in_year / 12.0) if months_in_year != 12 else controllable_opex
                
                controllable_recoverable = max(controllable_opex_full_year - cap_ceiling, 0.0)
                
                # Convert back to fractional for the recovery calculation
                controllable_recoverable_fractional = controllable_recoverable * (months_in_year / 12.0)
                recov = share * (noncontrollable_opex + controllable_recoverable_fractional) * occ_frac
                

            else:
                # Fallback: treat unknown types as NNN
                recov = share * (total_opex + property_tax) * occ_frac
                
            if np.isfinite(recov) and recov >= 0:
                total += recov
        except Exception:
            continue  # Skip this tenant if calculation fails
            
    return total if np.isfinite(total) else 0.0

# ============== core model ==============
def run_model(params=None, return_params_only=False):
    """
    Run a single Monte Carlo simulation with the given parameters.
    
    FIXES APPLIED:
    - Sale Month Logic: Now affects cash flow TIMING, not just amounts
      * Earlier months (1-6) result in higher IRR due to time value of money
      * Later months (7-12) result in lower IRR due to delayed cash flows
      * This ensures correct financial behavior for IRR calculations
    """
    p = default_params() if params is None else {**default_params(), **params}
    p = apply_preset(p)  # apply PRESET overrides, if any
    
    # CRITICAL FIX: Always reconstruct lease_roll to ensure WALT and other parameters are correctly applied
    # This ensures WALT changes actually affect the simulation
    p['lease_roll'] = _reconstruct_lease_roll(p)
    
    # If only parameters are requested, return them after processing
    if return_params_only:
        return p
    
    # CRITICAL FIX: Always reconstruct lease_roll to ensure WALT and other parameters are correctly applied
    # This ensures WALT changes actually affect the simulation
    p['lease_roll'] = _reconstruct_lease_roll(p)
    
    # Defensive copy of lease_roll to avoid mutating caller/shared structures
    if 'lease_roll' in p and isinstance(p['lease_roll'], list):
        p['lease_roll'] = [dict(t) for t in p['lease_roll']]
    if PRESET == 'market_logical':
        if HAS_RICH and console:
            console.print("[dim]Preset 'market_logical' applied: vacancy=true, taxes independent (2.5%), debt ratio=55%.[/dim]")
        else:
            print("Preset 'market_logical' applied: vacancy=true, taxes independent (2.5%), debt ratio=55%.")
    # --- per-run reproducible randomness ---
    seed_internal = p.get('_seed', None)
    # Seed legacy RNG used by np.random.* (sample_* helpers)
    if seed_internal is not None:
        np.random.seed(seed_internal)

    # Guardrails
    assert 0.0 <= p.get("debt_ratio", 0.0) <= 0.75, "debt_ratio must be between 0.00 and 0.75"

    # Local toggles (defaults keep economics unchanged)
    amort_gran = str(p.get('amortization_granularity','annual')).lower()
    cov_track = bool(p.get('covenant_track', False))
    cov_th = dict(p.get('covenant_thresholds', {'dscr_min':1.25,'dy_min':0.08,'ltv_max':0.65}))
    cov_action = str(p.get('covenant_action','warn')).lower()
    refi_box = dict(p.get('refi_boxes', {'enabled':False,'lockout_years':0,'max_ltv':0.65,'min_dscr':1.30,'min_dy':0.08}))
    prepay_cfg = dict(p.get('prepay', {'model': 'none', 'lockout_years': 0, 'stepdown': {}, 'ym_spread': 0.0}))
    prepay_model_str = str(prepay_cfg.get('model', 'none')).lower()
    # normalize common synonyms so branches ('ym','stepdown','defeasance') match
    if prepay_model_str in ('yield_maintenance', 'yield-maintenance', 'yieldmaintenance'):
        prepay_model_str = 'ym'
        prepay_cfg['model'] = 'ym'
    debug_sched = bool(p.get('debug_return_schedule', False))
    explain_mode = bool(p.get('explain_mode', False))

    # fixed per-run samples (allow param override for sensitivity)
    # Get triangular distribution parameters from UI or use defaults
    exit_cap_left = p.get('exit_cap_left', 0.075)
    exit_cap_mode = p.get('exit_cap_mode', 0.085)
    exit_cap_right = p.get('exit_cap_right', 0.090)
    
    exit_cap = sample_exit_cap_rate(left=exit_cap_left, mode=exit_cap_mode, right=exit_cap_right)
    if p.get('exit_cap_override') is not None:
        try:
            exit_cap = float(p.get('exit_cap_override'))
        except Exception:
            pass
    cost_over  = sample_cost_overrun()
    sale_year  = sample_sale_year()

    # project setup
    purchase_price        = p["purchase_price"]
    opex                  = p["operating_expenses_start"]
    opex_growth_rate      = p["opex_growth_rate"]
    property_tax_rate     = p["property_tax_rate"]
    total_cost            = purchase_price * (1 + cost_over)

    # debt
    debt_ratio            = p["debt_ratio"]
    interest_rate         = p["interest_rate"]
    loan_amount           = total_cost * debt_ratio
    principal_out         = loan_amount

    # day-0 cash items (affect equity)
    # FIX: RESERVE LOGIC CORRECTED TO ELIMINATE IRR SENSITIVITY
    # - Working Capital & Contingency: Added to equity, returned at sale (no IRR impact)
    # - Seller Reserve Credit: Subtracted from equity, not returned (credit, no IRR impact)
    # - This ensures reserves only affect initial investment amount, not cash flow timing
    acq_costs      = purchase_price * p["acq_cost_rate"]
    financing_fees = loan_amount * p["financing_fee_rate"]
    rate_cap_cost_param = p.get("rate_cap_cost", 0.0)
    # If provided < 1, interpret as a rate applied to loan_amount; otherwise treat as absolute dollars
    rate_cap_cost  = (loan_amount * rate_cap_cost_param) if rate_cap_cost_param < 1 else rate_cap_cost_param
    contingency    = p["contingency_reserve"]
    wc_reserve     = p["working_capital_reserve"]
    seller_credit  = p["seller_reserve_credit"]
    # Buyer-side transfer tax at acquisition (percent of purchase price)
    transfer_tax_buy = purchase_price * p.get("transfer_tax_buy_rate", 0.0)
    # Working capital true-up at close (fixed + % of first-year opex baseline)
    wc_true_up_close = float(p.get('wc_true_up_close_dollar', 0.0)) + float(p.get('wc_true_up_close_pct_of_opex', 0.0)) * float(opex)

    # equity needed at t0 (fund total cost basis + fees/reserves – loan – seller credit)
    # FIX: Seller Reserve Credit is subtracted from equity (correct behavior - no return at sale)
    equity = (total_cost
              + acq_costs
              + financing_fees
              + rate_cap_cost
              + contingency  # FIX: Added to equity, will be returned at sale
              + wc_reserve   # FIX: Added to equity, will be returned at sale
              + transfer_tax_buy
              + wc_true_up_close
              - seller_credit  # FIX: Subtracted from equity (credit, not returned)
              - loan_amount)

    io_years              = int(p["interest_only_years"])
    amort_years_total     = int(p["amort_years"])
    post_refi_io_years    = int(p["post_refi_io_years"])

    amort_started         = False
    amort_payment         = 0.0

    # refinance setup (disabled by default)
    refi_year       = p["refi_year"]
    refi_cost_rate  = p["refi_cost_rate"]
    refi_done       = False
    refi_block_reason = None

    # annual state
    value_index     = 1.0
    cash_flows_to_equity = []
    noi_history     = []
    year1_cash_flow = None
    year1_dscr      = None
    year1_tax       = None
    first_noi       = np.nan
    y1_cash_rent    = np.nan
    y1_income       = np.nan
    y1_opex_noi     = np.nan
    lease_state = None
    ti_spend = lc_spend = 0.0

    # persistent counter to support post-refi IO across multiple years
    post_refi_io_remaining = 0

    # per-year arrays for strict breakeven stability
    rent_gross_series = []
    vac_series        = []
    opex_series       = []
    tax_series        = []
    debtpay_series    = []
    capex_series      = []
    dscr_series = []
    dy_series   = []
    ltv_series  = []
    occ_series  = []
    phys_occ_series = []
    econ_occ_series = []
    renewal_event_count = 0
    lease_event_count = 0
    trace_event_years = []
    trace_event_types = []
    trace_noi_series = []
    trace_debt_service_series = []
    trace_capex_event_series = []
    trace_refi_cash_out_series = []

    # running total of capital improvements to be added to tax basis at sale
    capex_cumulative = 0.0

    # Reserve balance and capex bucket trackers
    reserves_balance = 0.0
    tilc_total = 0.0
    building_capex_total = 0.0
    reserves_accrued_total = 0.0
    


    # Year-1 bucket snapshots (for reporting/breakeven)
    y1_capex = None
    y1_tilc = 0.0
    y1_building = 0.0
    y1_reserves = 0.0

    # Debt schedule and covenant tracking (record-only; no cash impact unless you toggle boxes)
    debt_schedule = []  # list of dict rows, one per year
    debt_schedule_monthly = []  # optional detailed schedule when amortization_granularity='monthly'
    prepay_cost_total = 0.0
    defeasance_cost_refi = 0.0  # tracked separately for disclosure
    prepay_cost_sale = 0.0       # sale-time prepay penalty (optional)
    prepay_cost_sale_estimate = 0.0
    prepay_at_sale_used = False
    prepay_at_sale_toggle = bool(p.get('prepay_at_sale', False))
    prepay_model_str = str(prepay_cfg.get('model', 'none')).lower()
    defeasance_used = False
    covenant_breaches_count = 0
    covenant_first_breach_year = None

    def set_amort_payment(current_principal):
        """Calculate level amortization payment with safety checks."""
        if current_principal <= 0 or not np.isfinite(current_principal):
            return 0.0
        if interest_rate <= 0 or not np.isfinite(interest_rate):
            return 0.0
        if amort_years_total <= 0:
            return 0.0
            
        nper = max(amort_years_total, 1)
        try:
            return float(npf.pmt(rate=interest_rate, nper=nper, pv=-current_principal))
        except Exception:
            return 0.0

    rng = np.random.default_rng(seed_internal)
    # --- Correlations / latent market strength (Stage 2 with Stage 1 fallback) ---
    growth_tilt = 0.0
    debug_initial_occ = p.get('initial_occupancy', np.nan)
    occ_override = None
    z_occ = np.nan
    z_g = np.nan
    use_corr = False  # governs debug fields
    
    # --- DEBUG correlation tracking ---
    debug_corr_mode = None
    corr_offdiag = float('nan')
    
    # Stage 2: generalized correlations (optional)
    corr_cfg = dict(p.get('correlations', {}))
    use_corr_v2 = bool(corr_cfg.get('enabled', False))
    if use_corr_v2:
        use_corr = True  # ensure growth tilt / occupancy override paths engage for Stage 2
        vars_list = list(corr_cfg.get('variables', []))
        k = len(vars_list)
        M = corr_cfg.get('matrix', np.eye(k))
        
        # Validate correlation matrix before use
        is_valid, error_msg = validate_correlation_matrix(M, vars_list)
        if not is_valid:
            _smoke("corr_matrix_invalid", detail=error_msg, matrix=str(M))
            # Fall back to identity matrix (no correlations)
            M = np.eye(k)
            _smoke("corr_matrix_fallback", detail="Using identity matrix due to validation failure")
        
        M = np.array(M, dtype=float)
        if M.shape != (k, k):
            _smoke("corr_matrix_shape_mismatch", k=k, shape=str(M.shape))
            M = np.eye(k)

        # Cholesky (fallback to identity if not PD)
        try:
            L = np.linalg.cholesky(M)
            if DEBUG_NNN_RECOVERY:
                print(f"🔗 Stage 2 correlations: Successfully decomposed {k}x{k} matrix")
        except Exception as e:
            _smoke("corr_matrix_not_pd", detail=f"Cholesky failed: {e}; using identity")
            L = np.eye(k)
            if DEBUG_NNN_RECOVERY:
                print(f"⚠️  Stage 2 correlations: Cholesky failed, using identity matrix")

        seed_off = int(corr_cfg.get('seed_offset', 0))
        # Use a more robust seed isolation method
        if seed_internal is not None:
            # Create a unique seed for correlations using better hash function
            # Use a combination of base seed, offset, and a prime multiplier
            corr_seed = (seed_internal * 73856093 + seed_off * 19349663) % (2**32)
            rng_corr = np.random.default_rng(corr_seed)
        else:
            rng_corr = np.random.default_rng(seed_off)
        
        z = rng_corr.standard_normal(size=k)
        zc = L @ z  # correlated standard normals

        # Helper: fetch latent by variable name
        latent = {name: float(zc[i]) for i, name in enumerate(vars_list) if i < k}
        
        # --- Debug: store actual off-diagonal used between occ0 and rg_bias, and mode ---
        debug_corr_mode = 'stage2'
        if ('occ0' in vars_list) and ('rg_bias' in vars_list):
            i_occ = vars_list.index('occ0')
            i_rg  = vars_list.index('rg_bias')
            if M.shape == (k, k):
                try:
                    corr_offdiag = float(M[i_occ, i_rg])
                except Exception:
                    corr_offdiag = float('nan')


        # Map occ0 (normal → occupancy override)
        if 'occ0' in latent:
            lm_cfg = dict(p.get('latent_market', {})) # reuse mapping parameters from Stage 1
            occ_mean  = float(lm_cfg.get('occ_mean', p.get('initial_occupancy', 0.85)))
            occ_sigma = float(lm_cfg.get('occ_sigma', 0.08))
            occ_lo, occ_hi = lm_cfg.get('occ_clamp', (0.50, 0.98))
            z_occ = latent['occ0']
            occ_override = float(np.clip(occ_mean + occ_sigma * z_occ, occ_lo, occ_hi))
            
            if DEBUG_NNN_RECOVERY:
                print(f"🔗 Stage 2: occ0={z_occ:.3f} → occupancy={occ_override:.3f} (base={occ_mean:.3f}, σ={occ_sigma:.3f})")

        # Map rg_bias (normal → tilt in percentage points)
        if 'rg_bias' in latent:
            lm_cfg = dict(p.get('latent_market', {}))
            tilt_pp = float(lm_cfg.get('tilt_pp', 0.01))
            z_g = latent['rg_bias']
            growth_tilt = tilt_pp * z_g
            
            if DEBUG_NNN_RECOVERY:
                print(f"🔗 Stage 2: rg_bias={z_g:.3f} → growth_tilt={growth_tilt:.4f} (tilt_pp={tilt_pp:.4f})")

        # Map exit_cap_q (normal → uniform quantile → triangular inverse CDF)
        if ('exit_cap_q' in latent) and (p.get('exit_cap_override') is None):
            u_ec = _std_norm_cdf(latent['exit_cap_q'])
            exit_cap = sample_exit_cap_rate_from_quantile(u_ec)

        # Map rate_q (normal → uniform → interest rate band)
        if 'rate_q' in latent:
            band = corr_cfg.get('rate_band', None)
            if isinstance(band, (list, tuple)) and len(band) == 2:
                lo, hi = float(band[0]), float(band[1])
                if hi < lo:
                    lo, hi = hi, lo
                u_r = _std_norm_cdf(latent['rate_q'])
                interest_rate = lo + u_r * (hi - lo)
        # end Stage 2
    else:
        # Stage 1 fallback (original 2‑var linkage occ ↔ growth tilt)
        lm_cfg = dict(p.get('latent_market', {}))
        if bool(lm_cfg.get('enabled', False)):
            use_corr = True
            # NOTE: lm_cfg['rho'] is desired corr(vacancy, growth). Vacancy = 1 - occupancy.
            rho_target = float(lm_cfg.get('rho', -0.6))
            # Clamp to valid open interval to avoid non-PD covariance
            rho_target = max(min(rho_target, 0.999), -0.999)
            rho_latent = -rho_target  # corr(occupancy, growth) used in the draw
            
            # Validate the covariance matrix
            cov_matrix = [[1.0, rho_latent], [rho_latent, 1.0]]
            is_valid, error_msg = validate_correlation_matrix(cov_matrix, ['occ', 'growth'])
            if not is_valid:
                _smoke("latent_corr_matrix_invalid", detail=error_msg, rho=rho_target)
                # Fall back to no correlations
                use_corr = False
            else:
                cov = np.array(cov_matrix)
            seed_off = int(lm_cfg.get('seed_offset', 0))
            # Use robust seed isolation for Stage 1 correlations
            if seed_internal is not None:
                # Use different prime multipliers for Stage 1 vs Stage 2
                latent_seed = (seed_internal * 73856093 + seed_off * 19349663 + 12345) % (2**32)
                rng_latent = np.random.default_rng(latent_seed)
            else:
                rng_latent = np.random.default_rng(seed_off)
            try:
                z_occ, z_g = rng_latent.multivariate_normal([0.0, 0.0], cov)
            except Exception:
                _smoke("corr_stage1_not_pd", rho=float(rho_latent))
                z_occ, z_g = rng_latent.standard_normal(2)
             # Debug: stage1 correlation mode and offdiag
            debug_corr_mode = 'stage1'
            corr_offdiag = float(rho_latent)
            # occupancy shock
            occ_mean  = float(lm_cfg.get('occ_mean', p.get('initial_occupancy', 0.85)))
            occ_sigma = float(lm_cfg.get('occ_sigma', 0.08))
            occ_lo, occ_hi = lm_cfg.get('occ_clamp', (0.50, 0.98))
            occ_override = float(np.clip(occ_mean + occ_sigma * float(z_occ), occ_lo, occ_hi))
            # growth tilt
            tilt_pp = float(lm_cfg.get('tilt_pp', 0.01))
            growth_tilt = float(tilt_pp) * float(z_g)
        # else: keep defaults (no correlations)

    # Alias used in growth logic
    rg_bias = float(growth_tilt)

    # Track first-year random growth for breakeven calc
    first_year_rg = None
    rg_draws = []

    # --- Property tax state ---
    # Precompute tax mode and growth; add guard so large values are treated as percents
    tax_mode = p.get('tax_mode', 'rent_indexed')
    tax_growth_rate = p.get('tax_growth_rate', 0.02)
    if tax_mode == 'independent' and tax_growth_rate > 1:
        tax_growth_rate = tax_growth_rate / 100.0
        if HAS_RICH and console:
            console.print(f"[yellow]Warning: tax_growth_rate > 1 interpreted as percent; using {tax_growth_rate:.4f}[/yellow]")
        else:
            print(f"Warning: tax_growth_rate > 1 interpreted as percent; using {tax_growth_rate:.4f}")

    # Stateful assessed value (allows mid-hold reassessment); start at purchase price
    assessed_value_tax_state = purchase_price

    # Reassessment configuration and pending reset state
    reassess_cfg = dict(p.get('tax_reassessment', {}))
    reassess_on_refi  = bool(reassess_cfg.get('on_refi', False))
    reassess_on_sale  = bool(reassess_cfg.get('on_sale', False))
    assess_ratio      = float(reassess_cfg.get('assessment_ratio', 1.0))
    phase_in_years    = int(reassess_cfg.get('phase_in_years', 0))
    max_cap_pct       = reassess_cfg.get('max_increase_cap_pct', None)
    max_cap_pct       = (float(max_cap_pct) if max_cap_pct is not None else None)
    pending_target_assessed = None
    phase_in_remaining = 0

    # Apply latent occupancy override only if the caller didn't pass one explicitly
    if use_corr and (p.get('override_initial_occupancy') is None) and (occ_override is not None):
        p['override_initial_occupancy'] = float(occ_override)

    # Optional: adjust initial occupancy for sensitivity (without mutating inputs)
    if p.get('override_initial_occupancy') is not None:
        try:
            occ = float(p.get('override_initial_occupancy'))
            occ = max(0.0, min(1.0, occ))
            total_rsf_val = float(p.get('total_rsf', 0.0))
            new_roll = []
            for t in p.get('lease_roll', []):
                t2 = dict(t)
                name = t2.get('name', '')
                if bool(t2.get('is_vacancy_bucket', False)) or name.lower() == 'vacant':
                    t2['rsf'] = (1 - occ) * total_rsf_val
                elif name.lower() == 'top10+rest':
                    t2['rsf'] = occ * total_rsf_val
                new_roll.append(t2)
            p['lease_roll'] = new_roll
        except Exception:
            pass

    # Record the actual initial occupancy used (post-override)
    if p.get('override_initial_occupancy') is not None:
        try:
            debug_initial_occ = float(p['override_initial_occupancy'])
        except Exception:
            pass

    months_per_year = []
    # FIX: SALE MONTH LOGIC - Now affects cash flow TIMING, not just amounts
    # This ensures earlier sale months result in higher IRR (correct financial behavior)
    sale_month_param = p.get('sale_month', None)
    sale_timing_adjustment = 0.0  # Will be used to adjust cash flow timing
    
    for year in range(1, sale_year + 1):
        refi_cash_out_this_year = 0.0

        # Determine months to simulate in this model year (supports mid-year sale)
        months_in_year = 12
        if (year == sale_year) and isinstance(sale_month_param, (int, float)):
            try:
                m = int(sale_month_param)
                if 1 <= m <= 12:
                    months_in_year = m
                    # FIX: Calculate timing adjustment for IRR calculation
                    # Earlier months (1-6) should result in higher IRR due to time value of money
                    # Later months (7-12) should result in lower IRR due to delayed cash flows
                    if m <= 6:
                        # First half of year: cash flows come earlier (higher IRR)
                        sale_timing_adjustment = (6.5 - m) / 12.0  # Positive adjustment for earlier months
                    else:
                        # Second half of year: cash flows come later (lower IRR)
                        sale_timing_adjustment = (6.5 - m) / 12.0  # Negative adjustment for later months
            except Exception:
                pass
        months_per_year.append(months_in_year)
        # market growth for valuation/taxes and lease mark-to-market
        if 'market_rent_growth_min' in p and 'market_rent_growth_max' in p:
            gmin = float(p.get('market_rent_growth_min', 0.02))
            gmax = float(p.get('market_rent_growth_max', 0.04))
            # maintain ordering defensively
            if gmax < gmin:
                gmin, gmax = gmax, gmin
            if use_corr:
                gmin_b = gmin + rg_bias
                gmax_b = gmax + rg_bias
                # keep ordering & clip to [−0.05, +0.10] as a wide safety range
                lo_b = max(min(gmin_b, gmax_b), -0.05)
                hi_b = min(max(gmin_b, gmax_b), 0.10)
                rg = rng.uniform(lo_b, hi_b)
            else:
                rg = rng.uniform(gmin, gmax)
        else:
            # fallback for older configs that pass a single deterministic growth; still apply bias if enabled
            base_rg = float(p.get('market_rent_growth', 0.03))
            rg = float(np.clip(base_rg + (rg_bias if use_corr else 0.0), -0.05, 0.10))
        rg_draws.append(float(rg))
        if year == 1:
            first_year_rg = rg
        value_index *= (1 + rg)
        market_rent_psf = p['market_rent_psf'] * value_index

        # --- Property tax calculation (stateful; supports reassessment) ---
        # Grow assessed value according to tax_mode
        prev_assessed = assessed_value_tax_state
        if tax_mode == 'independent':
            assessed_value_tax_state = assessed_value_tax_state * (1 + tax_growth_rate)
        else:
            assessed_value_tax_state = assessed_value_tax_state * (1 + rg)

        # Apply any pending reassessment target (typically set by a refi in the prior year)
        if pending_target_assessed is not None:
            target = float(pending_target_assessed)
            if phase_in_remaining > 0:
                # Linear phase-in toward target
                step = (target - assessed_value_tax_state) / phase_in_remaining
                assessed_candidate = assessed_value_tax_state + step
                phase_in_remaining -= 1
                if phase_in_remaining == 0:
                    pending_target_assessed = None
            else:
                assessed_candidate = target
                pending_target_assessed = None

            # Optional annual increase cap during reset
            if max_cap_pct is not None:
                cap_ceiling = prev_assessed * (1 + max_cap_pct)
                assessed_value_tax_state = min(assessed_candidate, cap_ceiling)
            else:
                assessed_value_tax_state = assessed_candidate

        property_tax = assessed_value_tax_state * property_tax_rate

        # initialize lease state for year 1, then advance one year each loop
        if year == 1:
            lease_state = _init_lease_state(p)
        # advance the lease roll one year; returns cash rent and TILC spends
        (
            cash_rent,
            scheduled_contract_rent,
            occupied_rsf_months,
            renewal_events_this_year,
            lease_events_this_year,
            ti_spend,
            lc_spend,
            ending_vacant_rsf,
            lease_state,
        ) = _advance_one_year_lease_roll(
            p, lease_state, market_rent_psf, rng=rng, months=months_in_year, collect_stats=True
        )
        renewal_event_count += renewal_events_this_year
        lease_event_count += lease_events_this_year

        # opex growth (keep your previous logic)
        if year > 1:
            opex *= (1 + opex_growth_rate)

        # opex split for recoveries
        controllable_opex_full = opex * p.get('controllable_opex_pct', 0.70)
        noncontrollable_opex_full = opex - controllable_opex_full
        
        # FIX: SALE MONTH LOGIC - Use timing adjustment instead of just scaling amounts
        # This ensures cash flows maintain their economic value while adjusting timing for IRR
        if year == sale_year and sale_month_param is not None:
            # For sale year, use timing adjustment to affect IRR calculation
            # Earlier months = higher IRR due to time value of money
            # Later months = lower IRR due to delayed cash flows
            frac_year = 1.0  # Keep full economic value
            timing_multiplier = 1.0 + sale_timing_adjustment
        else:
            # For non-sale years, use normal fractional year logic
            frac_year = (months_in_year / 12.0)
            timing_multiplier = 1.0
        
        controllable_opex = controllable_opex_full * frac_year
        noncontrollable_opex = noncontrollable_opex_full * frac_year
        opex_for_noi = (controllable_opex_full + noncontrollable_opex_full) * frac_year
        
        # DEBUG: Print OPEX values for NNN recovery tracing
        if DEBUG_NNN_RECOVERY and year == 1:
            print(f"\n🔍 DEBUG YEAR {year} - OPEX CALCULATION:")
            print(f"   - Base opex: ${opex:,.0f}")
            print(f"   - Controllable opex (full year): ${controllable_opex_full:,.0f}")
            print(f"   - Non-controllable opex (full year): ${noncontrollable_opex_full:,.0f}")
            print(f"   - Fractional year: {frac_year:.3f}")
            print(f"   - Controllable opex (fractional): ${controllable_opex:,.0f}")
            print(f"   - Non-controllable opex (fractional): ${noncontrollable_opex:,.0f}")
            print(f"   - OPEX for NOI: ${opex_for_noi:,.0f}")
        

        
        # Store Year 1 OPEX values for base year calculations
        if year == 1:
            # Capture the base year OPEX values (full year, not fractional)
            base_year_controllable_opex_full = opex * p.get('controllable_opex_pct', 0.70)
            base_year_noncontrollable_opex_full = opex - base_year_controllable_opex_full
            base_year_total_opex_full = base_year_controllable_opex_full + base_year_noncontrollable_opex_full
            

            
            # Initialize base-year opex snapshots for BASE_YEAR / CAM_CAP tenants
            for item in lease_state:
                if str(item.get('recovery_type', 'NNN')).upper() in ('BASE_YEAR', 'CAM_CAP'):
                    # Set base year values to Year 1 values (full year, not fractional)
                    item['base_year_total_opex'] = base_year_total_opex_full
                    item['base_year_controllable_opex'] = base_year_controllable_opex_full
                    item['base_year_set_year'] = 1
        
        # Handle base year resets for existing tenants (e.g., after lease renewals)
        for item in lease_state:
            if str(item.get('recovery_type', 'NNN')).upper() in ('BASE_YEAR', 'CAM_CAP'):
                if item.get('reset_base_year_now'):
                    # Reset to current year values when explicitly requested (e.g., new lease term)
                    item['base_year_total_opex'] = controllable_opex + noncontrollable_opex
                    item['base_year_controllable_opex'] = controllable_opex
                    item['base_year_set_year'] = year
                    item['reset_base_year_now'] = False
        property_tax = property_tax * frac_year
        recoveries = _compute_recoveries(p, lease_state, controllable_opex, noncontrollable_opex, property_tax, year, months_in_year=months_in_year)
        income = cash_rent + recoveries
        noi = income - opex_for_noi - property_tax
        
        # DEBUG: Print recovery and NOI calculation for NNN recovery tracing
        if DEBUG_NNN_RECOVERY and year == 1:
            print(f"\n🔍 DEBUG YEAR {year} - RECOVERY & NOI CALCULATION:")
            print(f"   - Cash rent: ${cash_rent:,.0f}")
            print(f"   - Recoveries: ${recoveries:,.0f}")
            print(f"   - Total income: ${income:,.0f}")
            print(f"   - OPEX for NOI: ${opex_for_noi:,.0f}")
            print(f"   - Property tax: ${property_tax:,.0f}")
            print(f"   - Final NOI: ${noi:,.0f}")
            print(f"   - Recovery type: {[t.get('recovery_type') for t in lease_state]}")
            print(f"   - Tenant RSF: {[t.get('rsf') for t in lease_state]}")
            print(f"   - Pro-rata shares: {[t.get('pro_rata_share') for t in lease_state]}")
            print(f"   - Occupied months: {[t.get('occupied_months_this_year') for t in lease_state]}")
        noi_history.append(noi)
        if noi < 0:
            _smoke("noi_negative", year=year, noi=noi)
        # --- tripwire assertions (catch silent logic slips early) ---
        assert np.isfinite(noi), "NOI is NaN/inf"
        assert assessed_value_tax_state >= 0, "Assessed value went negative"
        assert property_tax >= 0, "Property tax < 0"

        # Record beginning balance for covenant metrics and schedule
        beg_balance_year = principal_out

        # debt service (respects initial IO window AND any post-refi IO window)
        use_io_this_year = ((not amort_started and year <= io_years) or (post_refi_io_remaining > 0))

        if use_io_this_year:
            interest_payment_annual = principal_out * interest_rate
            interest_payment = interest_payment_annual * frac_year
            principal_paydown = 0.0
            annual_debt_payment = interest_payment
            if post_refi_io_remaining > 0:
                post_refi_io_remaining -= 1
        else:
            if not amort_started:
                amort_payment = set_amort_payment(principal_out)
                amort_started = True
            interest_payment_annual = principal_out * interest_rate
            principal_paydown_annual = max(amort_payment - interest_payment_annual, 0.0)
            interest_payment = interest_payment_annual * frac_year
            principal_paydown = principal_paydown_annual * frac_year
            annual_debt_payment = interest_payment + principal_paydown
            # Prevent negative principal balance
            principal_paydown = min(principal_paydown, principal_out)
            principal_out = max(principal_out - principal_paydown, 0.0)

        # Record debt schedule (record-only, totals unchanged)
        debt_schedule.append({
            'year': year,
            'beg_balance': float(beg_balance_year),
            'interest': float(interest_payment),
            'principal': float(principal_paydown),
            'payment': float(annual_debt_payment),
            'end_balance': float(principal_out),
            'is_io': bool(use_io_this_year),
            'post_refi': bool(refi_done),
            'months': int(months_in_year),
        })
        # Optional monthly schedule (record-only; totals unchanged)
        if amort_gran == 'monthly' and debug_sched:
            months_count = max(int(months_in_year), 1)
            int_m = float(interest_payment) / months_count
            prin_m = float(principal_paydown) / months_count
            bal_m = float(beg_balance_year)
            for mth in range(1, months_count + 1):
                pay_m = int_m + prin_m
                end_m = max(bal_m - prin_m, 0.0)
                debt_schedule_monthly.append({
                    'year': year,
                    'month': mth,
                    'beg_balance': bal_m,
                    'interest': int_m,
                    'principal': prin_m,
                    'payment': pay_m,
                    'end_balance': end_m,
                    'is_io': bool(use_io_this_year),
                    'post_refi': bool(refi_done),
                })
                bal_m = end_m
        # tripwire: balance should never drift negative
        assert principal_out >= -1e-6, "Negative loan balance"

        # capture year-1 metrics
        if year == 1:
            year1_tax  = property_tax
            year1_dscr = safe_div(noi, annual_debt_payment)
            first_noi  = noi
            y1_cash_rent = float(cash_rent) if np.isfinite(cash_rent) else np.nan
            y1_income = float(income) if np.isfinite(income) else np.nan
            y1_opex_noi = float(opex_for_noi) if np.isfinite(opex_for_noi) else np.nan

        # (refi logic preserved; optional lender boxes & prepay penalties)
        if (refi_year > 0 and year == refi_year and not refi_done and noi > 0 and annual_debt_payment != 0 and exit_cap > 0):
            dscr_now   = safe_div(noi, annual_debt_payment)
            new_value  = safe_div(noi, exit_cap)
            # Size by stated debt_ratio; we may cap by LTV box below
            new_loan_raw = (new_value * debt_ratio) if (new_value and debt_ratio) else 0.0

            # Default LTV cap (legacy 75%); override if refi_boxes enabled
            ltv_cap = 0.75
            allow_refi = True
            block_reason = None

            if bool(refi_box.get('enabled', False)):
                ltv_cap = float(refi_box.get('max_ltv', ltv_cap))
                min_dscr = float(refi_box.get('min_dscr', 1.30))
                min_dy   = float(refi_box.get('min_dy', 0.08))
                lockout  = int(refi_box.get('lockout_years', 0))
                debt_yield_now = safe_div(noi, beg_balance_year)

                if year <= lockout:
                    allow_refi = False
                    block_reason = f"lockout_years={lockout}"
                elif (not np.isnan(dscr_now)) and dscr_now < min_dscr:
                    allow_refi = False
                    block_reason = f"DSCR {dscr_now:.2f} < {min_dscr:.2f}"
                elif (not np.isnan(debt_yield_now)) and debt_yield_now < min_dy:
                    allow_refi = False
                    block_reason = f"DebtYield {debt_yield_now:.2%} < {min_dy:.2%}"

            new_loan_ltv_cap = (new_value * ltv_cap) if new_value else 0.0
            new_loan = min(new_loan_raw, new_loan_ltv_cap)

            ltv_ok = safe_div(new_loan, new_value) <= ltv_cap if new_value else False

            if allow_refi and (dscr_now > 1.25) and ltv_ok and (new_loan > principal_out):
                # Optional prepayment penalties
                prepay_cost = 0.0
                prepay_model = str(prepay_cfg.get('model','none')).lower()
                prepay_lock = int(prepay_cfg.get('lockout_years', 0))
                if year <= prepay_lock and prepay_model != 'none':
                    allow_refi = False
                    block_reason = f"prepay lockout_years={prepay_lock}"
                if allow_refi and prepay_model == 'stepdown':
                    sd = dict(prepay_cfg.get('stepdown', {}))
                    if sd:
                        rate = _lookup_stepdown_rate(sd, year)
                        prepay_cost = float(rate) * float(principal_out)
                elif allow_refi and prepay_model == 'ym':
                    # Simplified yield maintenance proxy; conservative placeholder
                    ym_spread = float(prepay_cfg.get('ym_spread', 0.0))
                    rf_proxy = max(0.0, interest_rate - ym_spread)
                    prepay_cost = rf_proxy * float(principal_out) * 1.0  # 1-year proxy
                elif allow_refi and prepay_model == 'defeasance':
                    # Respect lockout similar to other models
                    if year <= prepay_lock:
                        allow_refi = False
                        block_reason = f"defeasance lockout_years={prepay_lock}"
                    else:
                        # Remaining schedule from AFTER this year's payment
                        io_remaining = max(int(io_years) - int(year), 0)
                        amort_years_elapsed = max(int(year) - int(io_years), 0)
                        amort_remaining = max(int(amort_years_total) - amort_years_elapsed, 0)
                        years_remaining = io_remaining + amort_remaining

                        # Optional open year: stop stream earlier if provided
                        open_at = prepay_cfg.get('defeasance_open_year', None)
                        if open_at is not None:
                            years_remaining = max(min(years_remaining, int(open_at) - int(year)), 0)

                        # Use current amort payment if known; else compute a level payment
                        am_pay = amort_payment if amort_payment > 0 else set_amort_payment(principal_out)

                        # Risk-free discounting inputs
                        df_method = str(prepay_cfg.get('df_method', 'flat'))
                        rf_flat   = float(prepay_cfg.get('rf_flat_rate', 0.045))
                        rf_curve  = dict(prepay_cfg.get('rf_curve', {}))

                        # PV of the remaining loan payment stream at risk-free
                        pv_stream = _pv_defeasance(
                            principal_out, interest_rate, am_pay,
                            years_remaining, io_remaining,
                            df_method=df_method, rf_flat=rf_flat, rf_curve=rf_curve
                        )

                        # Fees in bps of PV; cost = PV(stream) - balance + fees, floored at 0
                        fees = pv_stream * float(prepay_cfg.get('fees_bps', 30)) / 10_000.0
                        prepay_cost = max(pv_stream - float(principal_out) + fees, 0.0)
                        defeasance_cost_refi = prepay_cost
                        if prepay_model_str == 'defeasance' and prepay_cost > 0:
                            defeasance_used = True
                # Re-check allow_refi in case prepay lockout blocked it
                if allow_refi:
                    refi_costs    = new_loan * refi_cost_rate
                    refi_cash_out = new_loan - principal_out - refi_costs - prepay_cost
                    prepay_cost_total += prepay_cost
                    principal_out = new_loan
                    if post_refi_io_years > 0:
                        post_refi_io_remaining = post_refi_io_years
                        amort_started = False
                    else:
                        amort_payment = set_amort_payment(principal_out)
                        amort_started = True
                    refi_cash_out_this_year = refi_cash_out
                    refi_done = True
                    refi_block_reason = None
                    # Schedule tax reassessment off the new appraised value (effective next year by default)
                    if reassess_on_refi:
                        target_assessed = max((new_value or 0.0) * assess_ratio, 0.0)
                        # Defer reassessment to the next model year to avoid mid-year NOI/DSCR mismatch.
                        # We only schedule the reset via pending_target_assessed; current-year property_tax
                        # and recoveries remain as already computed.
                        pending_target_assessed = target_assessed
                        phase_in_remaining = max(phase_in_years, 0)
                else:
                    refi_done = False
                    refi_block_reason = block_reason
            else:
                # Either boxes failed, DSCR/LTV failed legacy checks, or sizing not accretive
                refi_done = False
                refi_block_reason = block_reason if 'block_reason' in locals() else "legacy_checks"

        # --- Capex buckets and reserves ---
        # Building/LL capex (scheduled improvements)
        building_capex_gross = p.get("capex_schedule", {}).get(year, 0.0)
        building_capex_gross = building_capex_gross * frac_year

        # Annual replacement reserve accrual (cash set-aside, default 0.0)
        reserve_per_rsf = p.get("reserve_per_rsf", 0.0)
        reserve_start = int(p.get("reserve_start_year", 1))
        reserve_escalation = p.get("reserve_escalation", 0.0)
        if year >= reserve_start and reserve_per_rsf > 0:
            reserve_accrual = reserve_per_rsf * p['total_rsf'] * ((1 + reserve_escalation) ** (year - reserve_start)) * frac_year
        else:
            reserve_accrual = 0.0

        # Update reserve balance
        reserves_balance += reserve_accrual

        # Optionally fund building capex from reserves
        if str(p.get("reserve_policy", "accrue_only")).lower() == "offset_building":
            reserve_use = min(reserves_balance, building_capex_gross)
            reserves_balance -= reserve_use
        else:
            reserve_use = 0.0

        building_capex_net = building_capex_gross - reserve_use

        # TILC capex (from leasing activity)
        tilc_capex = ti_spend + lc_spend

        # Track totals
        tilc_total += tilc_capex
        building_capex_total += building_capex_gross
        reserves_accrued_total += reserve_accrual

        # Improvements added to tax basis exclude reserve accruals (escrow)
        capex_cumulative += (building_capex_gross + tilc_capex)

        # Total cash capex outflow this year
        total_capex_cash_out = building_capex_net + tilc_capex + reserve_accrual

        # equity cash flow
        cf_year_operating = noi - annual_debt_payment - total_capex_cash_out
        cf_year = cf_year_operating + refi_cash_out_this_year

        # FIX: SALE MONTH LOGIC - Apply timing adjustment to affect IRR calculation
        # This ensures earlier sale months result in higher IRR (correct financial behavior)
        if year == sale_year and sale_month_param is not None:
            # Apply timing adjustment to cash flow for IRR calculation
            # Earlier months = higher IRR due to time value of money
            # Later months = lower IRR due to delayed cash flows
            cf_year_adjusted = (cf_year_operating * timing_multiplier) + refi_cash_out_this_year
            cash_flows_to_equity.append(cf_year_adjusted)
            trace_event_years.append(year)
            trace_event_types.append('operations+refi' if refi_cash_out_this_year else 'operations')
            trace_noi_series.append(float(noi) if np.isfinite(noi) else None)
            trace_debt_service_series.append(float(annual_debt_payment) if np.isfinite(annual_debt_payment) else None)
            trace_capex_event_series.append(float(total_capex_cash_out) if np.isfinite(total_capex_cash_out) else None)
            trace_refi_cash_out_series.append(float(refi_cash_out_this_year) if np.isfinite(refi_cash_out_this_year) else 0.0)
        else:
            # Normal cash flow (no timing adjustment)
            cash_flows_to_equity.append(cf_year)
            trace_event_years.append(year)
            trace_event_types.append('operations+refi' if refi_cash_out_this_year else 'operations')
            trace_noi_series.append(float(noi) if np.isfinite(noi) else None)
            trace_debt_service_series.append(float(annual_debt_payment) if np.isfinite(annual_debt_payment) else None)
            trace_capex_event_series.append(float(total_capex_cash_out) if np.isfinite(total_capex_cash_out) else None)
            trace_refi_cash_out_series.append(float(refi_cash_out_this_year) if np.isfinite(refi_cash_out_this_year) else 0.0)
        
        # DEBUG: Print cash flow calculation for NNN recovery tracing
        if DEBUG_NNN_RECOVERY and year == 1:
            print(f"\n🔍 DEBUG YEAR {year} - CASH FLOW CALCULATION:")
            print(f"   - NOI: ${noi:,.0f}")
            print(f"   - Annual debt payment: ${annual_debt_payment:,.0f}")
            print(f"   - Total capex cash out: ${total_capex_cash_out:,.0f}")
            print(f"   - Cash flow to equity: ${cf_year:,.0f}")
            print(f"   - Cash flows array length: {len(cash_flows_to_equity)}")
        # --- Smoke: strict breakeven occupancy check for current year ---
        rent_gross_curr = p['total_rsf'] * market_rent_psf * frac_year
        occ_required = safe_div(opex_for_noi + property_tax + annual_debt_payment + total_capex_cash_out, rent_gross_curr)
        occ_actual = min(max(safe_div(cash_rent, rent_gross_curr), 0.0), 1.0)
        if not np.isnan(occ_required) and occ_actual < occ_required:
            _smoke(
                "breakeven_occupancy",
                year=year,
                occ_actual=float(occ_actual),
                occ_required=float(occ_required)
            )

        # Covenant tracking (read-only; no cash impact)
        if cov_track:
            dscr_y = safe_div(noi, annual_debt_payment)
            dy_y   = safe_div(noi, beg_balance_year)
            ltv_y  = safe_div(principal_out, safe_div(noi, exit_cap)) if (exit_cap and noi) else np.nan
            breach = ((not np.isnan(dscr_y) and dscr_y < cov_th.get('dscr_min', 1.25)) or
                      (not np.isnan(dy_y) and dy_y < cov_th.get('dy_min', 0.08)) or
                      (not np.isnan(ltv_y) and ltv_y > cov_th.get('ltv_max', 0.65)))
            if breach:
                covenant_breaches_count += 1
                if covenant_first_breach_year is None:
                    covenant_first_breach_year = year
                _smoke(
                    "covenant_breach",
                    year=year,
                    dscr=float(dscr_y) if not np.isnan(dscr_y) else np.nan,
                    dscr_min=float(cov_th.get('dscr_min', 1.25)),
                    dy=float(dy_y) if not np.isnan(dy_y) else np.nan,
                    dy_min=float(cov_th.get('dy_min', 0.08)),
                    ltv=float(ltv_y) if not np.isnan(ltv_y) else np.nan,
                    ltv_max=float(cov_th.get('ltv_max', 0.65)),
                )
        
        # Store per-year path metrics (NaN allowed; we'll summarize safely later)
        try: dscr_series.append(float(dscr_y) if np.isfinite(dscr_y) else np.nan)
        except: dscr_series.append(np.nan)
        try: dy_series.append(float(dy_y) if np.isfinite(dy_y) else np.nan)
        except: dy_series.append(np.nan)
        try: ltv_series.append(float(ltv_y) if np.isfinite(ltv_y) else np.nan)
        except: ltv_series.append(np.nan)
        try: occ_series.append(float(occ_actual) if np.isfinite(occ_actual) else np.nan)
        except: occ_series.append(np.nan)
        try:
            total_rsf_denom = float(p['total_rsf']) * float(max(months_in_year, 1))
            phys_occ_rate_y = safe_div(occupied_rsf_months, total_rsf_denom)
            phys_occ_series.append(float(phys_occ_rate_y) if np.isfinite(phys_occ_rate_y) else np.nan)
        except Exception:
            phys_occ_series.append(np.nan)
        try:
            econ_occ_rate_y = safe_div(cash_rent, scheduled_contract_rent)
            econ_occ_series.append(float(econ_occ_rate_y) if np.isfinite(econ_occ_rate_y) else np.nan)
        except Exception:
            econ_occ_series.append(np.nan)

        # year-1 CoC & bucket snapshots
        if year == 1 and year1_cash_flow is None:
            year1_cash_flow = cf_year
            y1_capex = total_capex_cash_out
            y1_tilc = tilc_capex
            y1_building = building_capex_gross
            y1_reserves = reserve_accrual

        # collect series for stability test (use total capex cash outflow)
        rent_gross_series.append(p['total_rsf'] * market_rent_psf * frac_year)
        
        # Safe vacancy calculation with edge case handling
        rent_gross_denom = market_rent_psf * p['total_rsf'] * frac_year
        if rent_gross_denom > 0 and np.isfinite(rent_gross_denom):
            vacancy_rate = 1.0 - (cash_rent / rent_gross_denom)
            # Clamp vacancy to reasonable range [0, 1]
            vacancy_rate = max(0.0, min(1.0, vacancy_rate))
        else:
            vacancy_rate = 1.0  # Assume full vacancy if denominator is invalid
        
        vac_series.append(vacancy_rate)
        opex_series.append(opex_for_noi)
        tax_series.append(property_tax)
        debtpay_series.append(annual_debt_payment)
        capex_series.append(total_capex_cash_out)

    # terminal value & sale proceeds
    # Compute seller NOI (includes tax) and pre-tax NOI (adds tax back), annualized if partial-year
    if len(noi_history) == 0:
        avg_exit_noi = 0.0
        avg_pre_tax_noi = 0.0
    else:
        # Annualize last two years based on months_per_year captured in the loop
        ann_noi = []
        ann_tax = []
        for i, n in enumerate(noi_history):
            m = months_per_year[i] if i < len(months_per_year) else 12
            scale = (12.0 / m) if (m and m != 12) else 1.0
            ann_noi.append(float(np.nan_to_num(n, nan=0.0)) * scale)
            t_i = tax_series[i] if i < len(tax_series) else 0.0
            ann_tax.append(float(np.nan_to_num(t_i, nan=0.0)) * scale)

        if len(ann_noi) == 1:
            avg_exit_noi = ann_noi[-1]
            avg_pre_tax_noi = ann_noi[-1] + (ann_tax[-1] if ann_tax else 0.0)
        else:
            avg_exit_noi = float(np.nan_to_num(np.mean(ann_noi[-2:]), nan=0.0))
            avg_pre_tax_noi = float(np.nan_to_num(np.mean([n + t for n, t in zip(ann_noi[-2:], ann_tax[-2:])]), nan=0.0))

    # Buyer-priced exit toggle: if enabled and reassessment-at-sale is modeled, price with buyer's first-year tax
    use_buyer_priced = bool(p.get('price_terminal_with_buyer_tax', False)) and reassess_on_sale
    if use_buyer_priced:
        # Algebraic solution for circularity where buyer tax depends on sale price:
        # TV = PreTaxNOI / (exit_cap + property_tax_rate * assessment_ratio)
        denom = (exit_cap + (property_tax_rate * assess_ratio)) if (exit_cap and assess_ratio is not None) else exit_cap
        if denom and denom > 0:
            terminal_value = safe_div(avg_pre_tax_noi, denom)
        else:
            terminal_value = 0.0
        terminal_value_method = 'buyer_priced'
    else:
        if exit_cap and exit_cap > 0:
            terminal_value = safe_div(avg_exit_noi, exit_cap)
        else:
            terminal_value = 0.0
        terminal_value_method = 'seller_priced'
    
    # Ensure terminal value is finite and non-negative
    if not np.isfinite(terminal_value) or terminal_value < 0:
        terminal_value = 0.0

    # Seller-side transfer tax at sale (percent of terminal value)
    transfer_tax_sell = terminal_value * p.get("transfer_tax_sell_rate", 0.0)
    sale_costs = terminal_value * p["sale_cost_rate"] + transfer_tax_sell
    net_sale_before_debt_and_tax = terminal_value - sale_costs

    # --- Two tax views (disclosure only) ---
    # 1) "Simple" basis = original total_cost (purchase + any sampled overrun)
    simple_basis = total_cost
    gain_simple = net_sale_before_debt_and_tax - simple_basis
    tax_simple = gain_simple * 0.20 if gain_simple > 0 else 0.0

    # 2) "Capex-adjusted" basis = adds acq/financing costs, contingency, seller credit and cumulative capex
    tax_basis = (total_cost
                 + acq_costs
                 + financing_fees
                 + rate_cap_cost
                 + contingency
                 + transfer_tax_buy
                 - seller_credit
                 + capex_cumulative)
    gain_capex = net_sale_before_debt_and_tax - tax_basis
    tax_capex = gain_capex * 0.20 if gain_capex > 0 else 0.0

    # Cash economics use the capex-adjusted tax (conservative)
    # FIX: RESERVE RETURN LOGIC - ELIMINATES IRR SENSITIVITY
    # Working Capital Reserve: Returned at sale (already correct)
    # Contingency Reserve: Will be returned below (fixes IRR sensitivity)
    # Seller Reserve Credit: Not returned (credit, not reserve)
    net_sale_proceeds = (net_sale_before_debt_and_tax - tax_capex) - principal_out + p["working_capital_reserve"]
    # Working capital true-up at sale (fixed + % of sale-year opex annualized)
    try:
        m_last = months_per_year[-1] if months_per_year else 12
        opex_last_annualized = (opex_series[-1] * (12.0 / m_last)) if (opex_series and m_last) else 0.0
    except Exception:
        opex_last_annualized = 0.0
    wc_true_up_sale = float(p.get('wc_true_up_sale_dollar', 0.0)) + float(p.get('wc_true_up_sale_pct_of_opex', 0.0)) * float(opex_last_annualized)
    net_sale_proceeds += wc_true_up_sale
    # Optional prepayment penalty at sale (OFF by default)
    prepay_cost_sale = 0.0
    prepay_cost_sale_estimate = 0.0
    if bool(p.get('prepay_at_sale', False)):
        prepay_model = str(prepay_cfg.get('model', 'none')).lower()

        if prepay_model == 'stepdown':
            sd = dict(prepay_cfg.get('stepdown', {}))
            if sd:
                rate = _lookup_stepdown_rate(sd, sale_year)
                prepay_cost_sale = float(rate) * float(principal_out)

        elif prepay_model == 'ym':
            # Simplified yield maintenance proxy; conservative placeholder (same as refi branch)
            ym_spread = float(prepay_cfg.get('ym_spread', 0.0))
            rf_proxy = max(0.0, interest_rate - ym_spread)
            prepay_cost_sale = rf_proxy * float(principal_out) * 1.0  # 1-year proxy

        elif prepay_model == 'defeasance':
            # Remaining schedule from AFTER the sale year
            if refi_done:
                # post-refi IO window relative to sale timing
                io_rem = max(int(refi_year + post_refi_io_years) - int(sale_year), 0)
                amort_elapsed = max(int(sale_year) - int(refi_year + post_refi_io_years), 0)
            else:
                io_rem = max(int(io_years) - int(sale_year), 0)
                amort_elapsed = max(int(sale_year) - int(io_years), 0)

            amort_rem = max(int(amort_years_total) - amort_elapsed, 0)
            years_remaining = io_rem + amort_rem

            # Optional open year: stop stream earlier if provided
            open_at = prepay_cfg.get('defeasance_open_year', None)
            if open_at is not None:
                years_remaining = max(min(years_remaining, int(open_at) - int(sale_year)), 0)

            # Level amort payment for remaining term
            am_pay = amort_payment if amort_payment > 0 else set_amort_payment(principal_out)

            # Risk-free discounting inputs
            df_method = str(prepay_cfg.get('df_method', 'flat'))
            rf_flat = float(prepay_cfg.get('rf_flat_rate', 0.045))
            rf_curve = dict(prepay_cfg.get('rf_curve', {}))

            # PV of the remaining loan payment stream at risk-free
            pv_stream = _pv_defeasance(
                principal_out, interest_rate, am_pay,
                years_remaining, io_rem,
                df_method=df_method, rf_flat=rf_flat, rf_curve=rf_curve
            )

            # Fees in bps of PV; cost = PV(stream) - balance + fees, floored at 0
            fees = pv_stream * float(prepay_cfg.get('fees_bps', 30)) / 10_000.0
            prepay_cost_sale = max(pv_stream - float(principal_out) + fees, 0.0)

    # --- Sale-time prepay cost (estimate only when toggle is False) ---
    # Always compute a disclosure estimate into `prepay_cost_sale_estimate` without affecting proceeds
    model_lower = str(prepay_cfg.get('model', 'none')).lower()
    if model_lower == 'defeasance':
        # Remaining schedule from AFTER the sale year
        if refi_done:
            io_rem = max(int(refi_year + post_refi_io_years) - int(sale_year), 0)
            amort_elapsed = max(int(sale_year) - int(refi_year + post_refi_io_years), 0)
        else:
            io_rem = max(int(io_years) - int(sale_year), 0)
            amort_elapsed = max(int(sale_year) - int(io_years), 0)
        amort_rem = max(int(amort_years_total) - amort_elapsed, 0)
        years_remaining = io_rem + amort_rem
        open_at = prepay_cfg.get('defeasance_open_year', None)
        if open_at is not None:
            years_remaining = max(min(years_remaining, int(open_at) - int(sale_year)), 0)
        am_pay = amort_payment if amort_payment > 0 else set_amort_payment(principal_out)
        df_method = str(prepay_cfg.get('df_method', 'flat'))
        rf_flat = float(prepay_cfg.get('rf_flat_rate', 0.045))
        rf_curve = dict(prepay_cfg.get('rf_curve', {}))
        pv_stream = _pv_defeasance(
            principal_out, interest_rate, am_pay,
            years_remaining, io_rem,
            df_method=df_method, rf_flat=rf_flat, rf_curve=rf_curve
        )
        fees = pv_stream * float(prepay_cfg.get('fees_bps', 30)) / 10_000.0
        prepay_cost_sale_estimate = max(pv_stream - float(principal_out) + fees, 0.0)
    elif model_lower == 'ym':
        ym_spread = float(prepay_cfg.get('ym_spread', 0.0))
        rf_proxy = max(0.0, interest_rate - ym_spread)
        prepay_cost_sale_estimate = rf_proxy * float(principal_out) * 1.0
    elif model_lower == 'stepdown':
        sd = dict(prepay_cfg.get('stepdown', {}))
        if sd:
            rate = _lookup_stepdown_rate(sd, sale_year)
            prepay_cost_sale_estimate = float(rate) * float(principal_out)
    else:
        prepay_cost_sale_estimate = 0.0
    
    # Ensure estimate is always numeric
    prepay_cost_sale_estimate = max(float(prepay_cost_sale_estimate), 0.0)

    # Deduct sale-time prepay penalty from proceeds only if toggle is ON
    if bool(p.get('prepay_at_sale', False)):
        net_sale_proceeds -= prepay_cost_sale
        prepay_cost_sale = max(float(prepay_cost_sale), 0.0)
        prepay_at_sale_used = prepay_cost_sale > 0
    # Return unspent reserves to equity if we accrued them separately
    if str(p.get("reserve_policy", "accrue_only")).lower() == "accrue_only":
        net_sale_proceeds += reserves_balance
    
    # FIX: RESERVE RETURN LOGIC - COMPLETE IMPLEMENTATION
    # ===================================================
    # This fix eliminates IRR sensitivity to reserve parameters by ensuring
    # that reserves only affect initial equity requirements, not cash flow timing.
    #
    # Working Capital Reserve: Already returned above (line 1880) ✅
    # Contingency Reserve: Returned here (fixes IRR sensitivity) ✅
    # Seller Reserve Credit: Not returned (credit, not reserve) ✅
    #
    # Result: Reserves now only affect HOW MUCH capital is invested,
    #         not WHEN cash flows occur. IRR sensitivity eliminated.
    net_sale_proceeds += p["contingency_reserve"]

    if cash_flows_to_equity:
        # FIX: SALE MONTH LOGIC - Apply timing adjustment to sale proceeds for IRR calculation
        # This ensures earlier sale months result in higher IRR (correct financial behavior)
        if sale_month_param is not None:
            # Apply timing adjustment to sale proceeds for IRR calculation
            # Earlier months = higher IRR due to time value of money
            # Later months = lower IRR due to delayed cash flows
            net_sale_proceeds_adjusted = net_sale_proceeds * timing_multiplier
            cash_flows_to_equity[-1] += net_sale_proceeds_adjusted
        else:
            # Normal sale proceeds (no timing adjustment)
            cash_flows_to_equity[-1] += net_sale_proceeds

    # Disclosure: what assessed value would reset to upon sale (buyer year-1), if enabled
    assessed_value_after_sale = (terminal_value * assess_ratio) if reassess_on_sale else None

    # final cash flows & returns
    cash_flows = [-equity] + cash_flows_to_equity
    irr = calculate_irr(cash_flows)
    
    # Handle IRR calculation failures gracefully
    if not np.isfinite(irr):
        _smoke("irr_calculation_failed", cash_flows_length=len(cash_flows), equity=equity)
        irr = np.nan
    
    npv = calculate_npv(p["discount_rate"], cash_flows)

    # standard metrics
    coc_return      = safe_div(year1_cash_flow, equity)

    # Equity Multiple = (sum of POSITIVE equity distributions) / equity contributed
    pos_equity_dists = sum(cf for cf in cash_flows_to_equity if cf > 0)
    equity_multiple  = safe_div(pos_equity_dists, equity)

    # Yield on Cost = Y1 NOI / Total Cost basis
    yield_on_cost   = safe_div(first_noi, total_cost)

    cap_rate        = safe_div(first_noi, purchase_price)
    ltv_exit        = safe_div(principal_out, terminal_value) if terminal_value else np.nan
    dscr_y1         = year1_dscr

    # Risk metrics
    debt_yield_y1   = safe_div(first_noi, loan_amount)
    irr_capex_adj   = irr
    stabilized_yoc  = safe_div(avg_exit_noi, total_cost)

    # stricter break-even occupancy (Y1)
    # y1_capex was captured during the yearly loop from all capex buckets
    # Use the actual Year‑1 debt service that was used in cash flows for consistency.
    if debtpay_series:
        y1_debt_service = float(debtpay_series[0])
    else:
        # Fallback: compute based on IO vs amortization; respect amortization granularity
        if int(p.get("interest_only_years", 0)) >= 1:
            y1_debt_service = loan_amount * interest_rate
        else:
            amort_gran_calc = str(p.get('amortization_granularity', 'annual')).lower()
            if amort_gran_calc == 'monthly':
                y1_debt_service = 12.0 * float(npf.pmt(p["interest_rate"]/12.0, int(p["amort_years"]) * 12, -loan_amount))
            else:
                y1_debt_service = float(npf.pmt(p["interest_rate"], int(p["amort_years"]), -loan_amount))

    # Use scheduled in-place rent (full building at in-place rate), not market-indexed
    y1_gpr = p['total_rsf'] * p.get('in_place_rent_psf', p['market_rent_psf'])
    if y1_gpr <= 0 or not np.isfinite(y1_gpr):
        breakeven_occ_strict_y1 = np.nan
    else:
        breakeven_occ_strict_y1 = safe_div(p["operating_expenses_start"] + (year1_tax or 0.0) + y1_debt_service + y1_capex, y1_gpr)
    
    # Ensure breakeven occupancy is finite and reasonable
    if not np.isfinite(breakeven_occ_strict_y1) or breakeven_occ_strict_y1 < 0 or breakeven_occ_strict_y1 > 2:
        breakeven_occ_strict_y1 = np.nan

    # occupancy stability vs strict breakeven each year
    years_below_breakeven = 0
    for r_gross, vac, opx, tax, debtp, capx in zip(rent_gross_series, vac_series, opex_series, tax_series, debtpay_series, capex_series):
        occ_req = safe_div(opx + tax + debtp + capx, r_gross)  # strict breakeven for that year
        occ_actual = min(max(1.0 - vac, 0.0), 1.0)
        if np.isnan(occ_req) or np.isnan(occ_actual):
            continue
        if occ_actual < occ_req:
            years_below_breakeven += 1
    run_is_stable = (years_below_breakeven == 0)

    # --- Min DSCR / Min Debt Yield across the hold (lender-style worst year) ---
    if debt_schedule:
        payments = [row.get('payment', np.nan) for row in debt_schedule]
        beg_balances = [row.get('beg_balance', np.nan) for row in debt_schedule]
        dscr_list = [safe_div(n, pay) for n, pay in zip(noi_history, payments)]
        dy_list   = [safe_div(n, bal) for n, bal in zip(noi_history, beg_balances)]
        min_dscr = _nanmin_finite(dscr_list)
        min_debt_yield = _nanmin_finite(dy_list)
    else:
        min_dscr = np.nan
        min_debt_yield = np.nan

    # Compute NaN-safe summaries of per-year path metrics
    def _finite(vs): 
        return [float(x) for x in vs if np.isfinite(x)]

    _ds = _finite(dscr_series)
    _dy = _finite(dy_series)
    _lt = _finite(ltv_series)
    _oc = _finite(occ_series)
    _oc_phys = _finite(phys_occ_series)
    _oc_econ = _finite(econ_occ_series)

    dscr_min = min(_ds) if _ds else np.nan
    dscr_avg = (sum(_ds)/len(_ds)) if _ds else np.nan
    dy_min   = min(_dy) if _dy else np.nan
    ltv_max  = max(_lt) if _lt else np.nan
    occ_min  = min(_oc) if _oc else np.nan
    occ_avg  = (sum(_oc)/len(_oc)) if _oc else np.nan
    phys_occ_avg = (sum(_oc_phys)/len(_oc_phys)) if _oc_phys else np.nan
    econ_occ_avg = (sum(_oc_econ)/len(_oc_econ)) if _oc_econ else np.nan

    try:
        grm = safe_div(purchase_price, y1_cash_rent) if (np.isfinite(y1_cash_rent) and y1_cash_rent > 0) else np.nan
    except Exception:
        grm = np.nan
    try:
        oer = safe_div(y1_opex_noi, y1_income) if (np.isfinite(y1_income) and y1_income > 0) else np.nan
    except Exception:
        oer = np.nan
    try:
        equity_to_value = safe_div(equity, total_cost) if (np.isfinite(total_cost) and total_cost > 0) else np.nan
    except Exception:
        equity_to_value = np.nan
    try:
        capex_total_kpi = float(sum(capex_series)) if capex_series else 0.0
    except Exception:
        capex_total_kpi = np.nan
    try:
        lease_renewal_rate = safe_div(renewal_event_count, lease_event_count) if lease_event_count > 0 else np.nan
    except Exception:
        lease_renewal_rate = np.nan

    # Debug: realized mean rent growth and initial occupancy used
    rg_mean = float(np.mean(rg_draws)) if rg_draws else np.nan
    result = {
        'IRR': irr,
        'IRR_CapexAdj': irr_capex_adj,
        'NPV': npv,
        'CoC': coc_return,
        'EquityMultiple': equity_multiple,
        'YieldOnCost': yield_on_cost,
        'Stabilized_YoC': stabilized_yoc,
        'CapRate': cap_rate,
        'LTV': ltv_exit,
        'DSCR': dscr_y1,
        'DebtYield_Y1': debt_yield_y1,
        'BreakEvenOcc': breakeven_occ_strict_y1,  # strict version
        'WALT': p.get('walt_years', np.nan),
        'YearsBelowBreakeven': years_below_breakeven,
        'RunStableAllYears': run_is_stable,
        'Equity': equity,  # Initial equity check at close; enables PI = (NPV + Equity) / Equity
        'ExitCap': float(exit_cap) if np.isfinite(exit_cap) else np.nan,
        'GRM': grm,
        'OperatingExpenseRatio': oer,
        'EquityToValue': equity_to_value,
        'Capex_Total': capex_total_kpi,
        'PhysicalOccupancyRate': phys_occ_avg,
        'EconomicOccupancyRate': econ_occ_avg,
        'LeaseRenewalRate': lease_renewal_rate,
        # --- Capex/Reserve reporting (buckets, for disclosure only) ---
        'Capex_TILC_Total': tilc_total,
        'Capex_Building_Total': building_capex_total,
        'Reserves_Accrued_Total': reserves_accrued_total,
        'Reserves_Ending_Balance': reserves_balance,
        'Y1_Capex_TILC': y1_tilc,
        'Y1_Capex_Building': y1_building,
        'Y1_Reserves': y1_reserves,
        # Disclosure-only sale/tax details
        'TerminalValue': terminal_value,
        'TerminalValue_Method': terminal_value_method,
        'BuyerPricedExit_Used': bool(p.get('price_terminal_with_buyer_tax', False)) and reassess_on_sale,
        'SaleCosts': sale_costs,
        'TransferTax_Buy': transfer_tax_buy,
        'TransferTax_Sell': transfer_tax_sell,
        'WCTrueUp_Close': wc_true_up_close,
        'WCTrueUp_Sale': wc_true_up_sale,
        'Gain_Simple': gain_simple,
        'Tax_Simple': tax_simple,
                # --- Correlation/latent debug fields (always included) ---
        '_Debug_Corr_Mode': debug_corr_mode,
        '_Debug_Corr_OffDiag': corr_offdiag,
        '_Debug_InitialOccupancy': float(debug_initial_occ) if np.isfinite(float(debug_initial_occ)) else np.nan,
        '_Debug_RG_Bias': float(rg_bias),
        '_Debug_RG_Mean': float(rg_mean),
        '_Debug_Latent_Z_Occ': float(z_occ) if np.isfinite(z_occ) else np.nan,
        '_Debug_Latent_Z_Growth': float(z_g) if np.isfinite(z_g) else np.nan,
        'Gain_CapexAdj': gain_capex, 
        'Tax_CapexAdj': tax_capex,
        'AssessedValue_Tax_LastYear': assessed_value_tax_state,
        'AssessedValue_Reset_At_Sale': assessed_value_after_sale,
        # --- Debt/covenant/refi summary ---
        'Debt_BegBal_Y1': debt_schedule[0]['beg_balance'] if debt_schedule else np.nan,
        'Debt_EndBal_Exit': debt_schedule[-1]['end_balance'] if debt_schedule else np.nan,
        'Debt_TotalInterest': sum(row['interest'] for row in debt_schedule),
        'Refi_Executed': bool(refi_done),
        'Refi_Block_Reason': refi_block_reason,
        'Prepay_Model': prepay_model_str,
        'Prepay_Cost_Total': float(prepay_cost_total),
        'Defeasance_Cost_Refi': float(defeasance_cost_refi),
        'Prepay_Cost_Sale': float(prepay_cost_sale),
        'Prepay_Cost_Sale_Estimate': float(prepay_cost_sale_estimate),
        'Defeasance_Used': bool(defeasance_used),
        'PrepayAtSale_Used': bool(prepay_at_sale_used),
        'PrepayAtSale_Toggle': bool(prepay_at_sale_toggle),
        'Covenant_Breaches_Count': covenant_breaches_count,
        'Covenant_First_Breach_Year': covenant_first_breach_year,
        'MinDSCR': min_dscr,
        'MinDebtYield': min_debt_yield,
        'DSCR_Y1': float(year1_dscr) if (year1_dscr is not None and np.isfinite(year1_dscr)) else None,
        'NOI_Y1': float(noi_history[0]) if (len(noi_history) >= 1 and np.isfinite(noi_history[0])) else None,
        'DebtPayment_Y1': float(debt_schedule[0]['payment']) if (debt_schedule and np.isfinite(debt_schedule[0].get('payment', np.nan))) else None,
        **({'DebtSchedule': debt_schedule} if debug_sched else {}),
        'DebtScheduleGranularity': amort_gran,
        **({'DebtScheduleMonthly': debt_schedule_monthly} if (debug_sched and amort_gran == 'monthly') else {}),
        'PropertyTaxSeries': [float(x) for x in tax_series],
        # Path summaries (always returned)
        'DSCR_Min': dscr_min,
        'DSCR_Avg': dscr_avg,
        'DebtYield_Min': dy_min,
        'LTV_Max': ltv_max,
        'Occupancy_Min': occ_min,
        'Occupancy_Avg': occ_avg,

    }

    # Optional: return full series only when covenant tracking is on
    if bool(p.get('covenant_track', False)):
        result.update({
            'DSCR_Series': dscr_series,
            'DebtYield_Series': dy_series,
            'LTV_Series': ltv_series,
            'Occupancy_Series': occ_series,
        })

    if explain_mode:
        terminal_noi_basis = avg_pre_tax_noi if use_buyer_priced else avg_exit_noi
        reserve_return = reserves_balance if str(p.get("reserve_policy", "accrue_only")).lower() == "accrue_only" else 0.0
        terminal_data = {
            'noi_basis': float(terminal_noi_basis) if np.isfinite(terminal_noi_basis) else None,
            'exit_cap_rate': float(exit_cap) if np.isfinite(exit_cap) else None,
            'gross_sale_price': float(terminal_value) if np.isfinite(terminal_value) else None,
            'sale_costs': float(sale_costs) if np.isfinite(sale_costs) else None,
            'net_sale_before_debt_and_tax': float(net_sale_before_debt_and_tax) if np.isfinite(net_sale_before_debt_and_tax) else None,
            'sale_tax': float(tax_capex) if np.isfinite(tax_capex) else None,
            'debt_payoff': float(principal_out) if np.isfinite(principal_out) else None,
            'prepay_cost': float(prepay_cost_sale) if np.isfinite(prepay_cost_sale) else None,
            'wc_reserve_return': float(p["working_capital_reserve"]) if np.isfinite(p["working_capital_reserve"]) else None,
            'wc_true_up_sale': float(wc_true_up_sale) if np.isfinite(wc_true_up_sale) else None,
            'reserve_return': float(reserve_return) if np.isfinite(reserve_return) else None,
            'contingency_return': float(p["contingency_reserve"]) if np.isfinite(p["contingency_reserve"]) else None,
            'net_sale_proceeds': float(net_sale_proceeds) if np.isfinite(net_sale_proceeds) else None,
        }
        explain_identity = {
            'derived_seed': int(seed_internal) if seed_internal is not None else None,
            'run_index': int(p['_RunIndex']) if p.get('_RunIndex') is not None else None,
            'scenario': p.get('scenario') or p.get('scenario_name'),
            'preset': PRESET,
        }
        schedule_data = {
            'years': [int(y) for y in trace_event_years],
            'event_types': list(trace_event_types),
            'noi': list(trace_noi_series),
            'debt_service': list(trace_debt_service_series),
            'capex': list(trace_capex_event_series),
            'refi_cash_out': list(trace_refi_cash_out_series),
            'cash_flows': [float(x) for x in cash_flows_to_equity],
            'cash_flows_to_equity': [float(x) for x in cash_flows_to_equity],
        }
        result.update({
            '_ExplainMode': True,
            '_ExplainIdentity': explain_identity,
            '_ScheduleData': schedule_data,
            '_TerminalData': terminal_data,
            'equity_cf': [float(x) for x in cash_flows],
            '_CashFlowSeries': [float(x) for x in cash_flows],
        })

    return result

# ===== helper for parallel reproducibility =====
def _run_one_with_seed(i, base_seed, params):
    # Derive a unique, deterministic seed per task from base_seed and i
    if base_seed is None:
        # No global seed provided: allow nondeterministic run, but keep API consistent
        np.random.seed(None)
        return run_model(params={**(params or {}), '_seed': None})

    try:
        # Mix base_seed with i using a 32-bit hash (golden-ratio constant) for good dispersion
        seed_for_run = int(np.uint32(base_seed) ^ np.uint32(i * 0x9E3779B1))
    except Exception:
        # Very defensive fallback
        seed_for_run = (int(base_seed) + int(i) * 1000003) & 0xFFFFFFFF

    # Seed legacy RNG used by any np.random.* callers (e.g., sampling helpers)
    np.random.seed(seed_for_run)
    # Also pass the exact same seed into run_model so its default_rng uses the same value
    return run_model(params={**(params or {}), '_seed': seed_for_run})

# ============== simulation ==============
def run_simulation(n=1000, seed=None, params=None, parallel=False):
    """Run n independent simulations deterministically; stable across serial/parallel."""
    base_params = default_params() if params is None else {**default_params(), **params}

    # Deterministic, distinct seeds per run
    base = 0 if seed is None else int(seed)
    seeds = [base + i*10007 + 7919 for i in range(int(n))]

    def _one(i, s):
        # Pass a unique seed into run_model to isolate RNG per path
        res = run_model({**base_params, '_seed': s})
        res['_RunIndex'] = i  # preserve intended order
        return res

    pairs = list(enumerate(seeds))

    if parallel and 'HAS_JOBLIB' in globals() and HAS_JOBLIB:
        rows = Parallel(n_jobs=-1)(delayed(_one)(i, s) for (i, s) in pairs)
    else:
        rows = [_one(i, s) for (i, s) in pairs]

    df = pd.DataFrame(rows)
    if '_RunIndex' in df.columns:
        df = df.sort_values('_RunIndex').reset_index(drop=True)
    return df

# ============== analysis ==============
def analyze(df):
    if df.empty:
        print("No valid runs to analyze. Try loosening assumptions or check inputs.")
        return

    if HAS_RICH and console:
        console.print(Panel("IRR Summary", style="cyan"))
    print(df['IRR'].describe(percentiles=[0.05, 0.5, 0.95]))

    hit_target = (df['IRR'] >= 0.15).mean() * 100
    print(f"\nProbability IRR ≥ 15%: {hit_target:.2f}%")

    print("\n=== Additional Metrics (Averages) ===")
    print(f"Avg Cash-on-Cash Return: {df['CoC'].mean():.2%}  | Acceptable: {'Yes' if df['CoC'].mean() >= 0.08 else 'No'}  # ≥ 8%")
    print(f"Avg Equity Multiple:     {df['EquityMultiple'].mean():.2f}x   | Acceptable: {'Yes' if df['EquityMultiple'].mean() >= 1.8 else 'No'}  # ≥ 1.8x")
    print(f"Avg NPV:                 ${df['NPV'].mean():,.0f}")
    # Show NPV distribution percentiles to communicate downside/typical/upside
    try:
        npv_p5, npv_p50, npv_p95 = np.percentile(df['NPV'].dropna().values, [5, 50, 95])
        print(f"NPV percentiles:         5%=${npv_p5:,.0f} | 50%=${npv_p50:,.0f} | 95%=${npv_p95:,.0f}")
    except Exception:
        # REASON: guard against edge cases where NPV might be missing
        pass

    # Profitability Index (PI) using Equity returned per run: PI = (NPV + Equity)/Equity
    if 'Equity' in df.columns:
        try:
            pi = (df['NPV'] + df['Equity']) / df['Equity']
            print(f"Avg PI:                  {pi.mean():.2f}")
            # Optional distribution to mirror other metrics
            try:
                pi_p5, pi_p50, pi_p95 = np.percentile(pi.dropna().values, [5, 50, 95])
                print(f"PI percentiles:         5%={pi_p5:.2f} | 50%={pi_p50:.2f} | 95%={pi_p95:.2f}")
            except Exception:
                pass
        except Exception:
            pass

    # Show Equity Multiple distribution percentiles (5/50/95)
    try:
        em_p5, em_p50, em_p95 = np.percentile(df['EquityMultiple'].dropna().values, [5, 50, 95])
        print(f"Equity Multiple pctls:   5%={em_p5:.2f} | 50%={em_p50:.2f} | 95%={em_p95:.2f}")
    except Exception:
        # REASON: guard against edge cases where EquityMultiple might be missing
        pass

    # Show Cash-on-Cash (CoC) distribution percentiles (5/50/95)
    try:
        coc_p5, coc_p50, coc_p95 = np.percentile(df['CoC'].dropna().values, [5, 50, 95])
        print(f"CoC percentiles:         5%={coc_p5:.2%} | 50%={coc_p50:.2%} | 95%={coc_p95:.2%}")
    except Exception:
        # REASON: guard against edge cases where CoC might be missing
        pass
    print(f"Avg Yield on Cost:       {df['YieldOnCost'].mean():.2%}  | Acceptable: {'Yes' if df['YieldOnCost'].mean() >= 0.065 else 'No'}  # ≥ 6.5%")
    print(f"Avg Going-in Cap Rate:   {df['CapRate'].mean():.2%}  | Informational")
    print(f"Avg LTV at Exit:         {df['LTV'].mean():.2%}  | Acceptable: {'Yes' if df['LTV'].mean() <= 0.75 else 'No'}  # ≤ 75%")
    print(f"Avg DSCR (Year 1):       {df['DSCR'].mean():.2f}  | Acceptable: {'Yes' if df['DSCR'].mean() >= 1.25 else 'No'}  # ≥ 1.25")
    print(f"Avg Break-even Occ.:     {df['BreakEvenOcc'].mean():.2%}  | Acceptable: {'Yes' if df['BreakEvenOcc'].mean() <= 0.85 else 'No'}  # ≤ 85%")

    print("\n=== Risk & Return Metrics (Averages) ===")
    print(f"Avg Debt Yield (Year 1): {df['DebtYield_Y1'].mean():.2%}  | Rule of thumb ≥ 8–10%")
    print(f"Avg Stabilized YoC:      {df['Stabilized_YoC'].mean():.2%}  | Avg of last-2 NOI / Total Cost")
    print(f"Avg IRR (Capex-Adj.):    {df['IRR_CapexAdj'].mean():.2%}   | Same as IRR here (capex already modeled)")
    # Lender-style worst-year cushions (computed per run in run_model)
    if 'MinDSCR' in df.columns:
        try:
            print(f"Avg Min DSCR:           {df['MinDSCR'].mean():.2f}x  | % runs < 1.25x: {(df['MinDSCR'] < 1.25).mean()*100:.2f}%")
            md_p5, md_p50, md_p95 = np.percentile(df['MinDSCR'].dropna().values, [5, 50, 95])
            print(f"Min DSCR pctls:         5%={md_p5:.2f} | 50%={md_p50:.2f} | 95%={md_p95:.2f}")
        except Exception:
            pass
    if 'MinDebtYield' in df.columns:
        try:
            print(f"Avg Min Debt Yield:     {df['MinDebtYield'].mean():.2%}")
            mdy_p5, mdy_p50, mdy_p95 = np.percentile(df['MinDebtYield'].dropna().values, [5, 50, 95])
            print(f"Min DY pctls:           5%={mdy_p5:.2%} | 50%={mdy_p50:.2%} | 95%={mdy_p95:.2%}")
        except Exception:
            pass
    print(f"Reported WALT (yrs):     {df['WALT'].mean():.2f}           | Input (not simulated)")
    print(f"% Runs Stable All Years: {(df['RunStableAllYears'].mean()*100):.2f}%  | Occupancy ≥ strict breakeven every year")
    print(f"Avg Years < Breakeven:   {df['YearsBelowBreakeven'].mean():.2f} yrs  | Lower is better")
    # --- Prepay / Defeasance Usage ---
    try:
        n = len(df)
        def_used = (df['Defeasance_Used'].mean()*100) if 'Defeasance_Used' in df.columns else 0.0
        sale_used = (df['PrepayAtSale_Used'].mean()*100) if 'PrepayAtSale_Used' in df.columns else 0.0

        def_cost_avg = float(df.loc[df.get('Defeasance_Used', False) == True, 'Defeasance_Cost_Refi'].mean()) if 'Defeasance_Cost_Refi' in df.columns and 'Defeasance_Used' in df.columns and df['Defeasance_Used'].any() else 0.0
        sale_cost_avg = float(df.loc[df.get('PrepayAtSale_Used', False) == True, 'Prepay_Cost_Sale'].mean()) if 'Prepay_Cost_Sale' in df.columns and 'PrepayAtSale_Used' in df.columns and df['PrepayAtSale_Used'].any() else 0.0

        print("\n=== Prepay / Defeasance Usage ===")
        print(f"Defeasance used at refi: {def_used:.2f}% of runs | Avg cost when used: ${def_cost_avg:,.0f}")
        print(f"Prepay-at-sale applied:  {sale_used:.2f}% of runs | Avg cost when used: ${sale_cost_avg:,.0f}")

        if 'Prepay_Model' in df.columns:
            try:
                print(f"Most common prepay model: {df['Prepay_Model'].mode().iat[0]}")
            except Exception:
                pass
        if 'PrepayAtSale_Toggle' in df.columns:
            try:
                print(f"'prepay_at_sale' toggle ON in: {df['PrepayAtSale_Toggle'].mean()*100:.2f}% of runs")
            except Exception:
                pass
    except Exception:
        pass

    
    # Matplotlib histogram (interactive via Python UI; no file saves, no browser)
    irr_series = df['IRR'].dropna()
    if irr_series.empty:
        print("No IRR values to plot.")
        return

    # Dynamic bins and robust x-limits (1st–99th pct with padding)
    n_obs = len(irr_series)
    bins = max(30, int(np.sqrt(n_obs)))
    q1, q99 = np.nanpercentile(irr_series, [1, 99])
    pad = 0.01
    x_min = max(0.0, q1 - pad)
    x_max = q99 + pad

    mean_irr = irr_series.mean()
    median_irr = irr_series.median()

    plt.figure(figsize=(10, 6))
    sns.histplot(irr_series, bins=bins, kde=True)
    plt.title("IRR Distribution")
    plt.xlabel("IRR")
    plt.ylabel("Frequency")
    plt.gca().xaxis.set_major_formatter(mticker.PercentFormatter(1.0))



    # Markers: target, mean, median
    plt.axvline(TARGET_IRR, linestyle='--', linewidth=1, label=f"Target {TARGET_IRR:.0%}")
    plt.axvline(mean_irr, linestyle='-', linewidth=1, label=f"Mean {mean_irr:.1%}")
    plt.axvline(median_irr, linestyle=':', linewidth=1, label=f"Median {median_irr:.1%}")
    plt.legend(frameon=False, loc='upper right')
    plt.tight_layout()
    plt.show()


def save_sensitivity_tables(base_params=None, sens_n=300, seed=44, output_prefix=None):
    """
    Generate and SHOW (via matplotlib) two 2D sensitivity heatmaps of mean IRR:
      1) Exit Cap × Rent Growth
      2) Vacancy × Interest Rate

    No files are saved and no browser windows are opened.
    """
    base_params = dict(base_params or {})

    # -------- Heatmap 1: Exit Cap × Rent Growth --------
    exit_caps   = np.linspace(0.07, 0.095, 11)   # 7.0% to 9.5%
    rent_growth = np.linspace(0.01, 0.05, 9)     # 1% to 5%

    Z1 = np.full((len(exit_caps), len(rent_growth)), np.nan)
    for i, cap in enumerate(exit_caps):
        for j, g in enumerate(rent_growth):
            params = {
                **base_params,
                'exit_cap_override': cap,
                'market_rent_growth_min': g,
                'market_rent_growth_max': g,
                'debug_return_schedule': False,  # avoid building/returning schedules in sensitivities
            }
            df = run_simulation(n=sens_n, seed=seed, params=params, parallel=False)
            Z1[i, j] = df['IRR'].mean() if (isinstance(df, pd.DataFrame) and not df.empty) else np.nan

    # Plot: Exit Cap × Rent Growth (annotated, diverging colormap)
    df_plot1 = pd.DataFrame(
        Z1,
        index=[f"{v:.1%}" for v in exit_caps],
        columns=[f"{v:.1%}" for v in rent_growth],
    )
    plt.figure(figsize=(11, 7))
    ax1 = sns.heatmap(
        df_plot1,
        cmap='RdYlGn',
        vmin=HEATMAP_RANGE[0], vmax=HEATMAP_RANGE[1], center=TARGET_IRR,
        annot=True, fmt='.1%',
        linewidths=0.5, linecolor='white',
        cbar=True
    )
    # Percent-format the colorbar
    if ax1.collections and ax1.collections[0].colorbar:
        ax1.collections[0].colorbar.formatter = mticker.PercentFormatter(1.0)
        ax1.collections[0].colorbar.update_ticks()
    ax1.set_title('Mean IRR Sensitivity: Exit Cap × Rent Growth (centered at target)')
    ax1.set_xlabel('Rent Growth (annual)')
    ax1.set_ylabel('Exit Cap Rate')
    plt.tight_layout()
    plt.show()

    # -------- Heatmap 2: Vacancy × Interest Rate --------
    vacancy_rates = np.linspace(0.05, 0.25, 9)   # 5% to 25% vacancy
    int_rates     = np.linspace(0.05, 0.09, 9)   # 5% to 9% interest

    Z2 = np.full((len(vacancy_rates), len(int_rates)), np.nan)
    for i, vac in enumerate(vacancy_rates):
        occ = max(0.0, min(1.0, 1.0 - float(vac)))
        for j, r in enumerate(int_rates):
            params = {
                **base_params,
                'override_initial_occupancy': occ,   # sensitivity on starting occupancy (1 - vacancy)
                'interest_rate': float(r),
                'debug_return_schedule': False,      # avoid building/returning schedules in sensitivities
            }
            df = run_simulation(n=sens_n, seed=seed, params=params, parallel=False)
            Z2[i, j] = df['IRR'].mean() if (isinstance(df, pd.DataFrame) and not df.empty) else np.nan

    # Plot: Vacancy × Interest Rate (annotated, diverging colormap)
    df_plot2 = pd.DataFrame(
        Z2,
        index=[f"{v:.0%}" for v in vacancy_rates],
        columns=[f"{v:.1%}" for v in int_rates],
    )
    plt.figure(figsize=(11, 7))
    ax2 = sns.heatmap(
        df_plot2,
        cmap='RdYlGn',
        vmin=HEATMAP_RANGE[0], vmax=HEATMAP_RANGE[1], center=TARGET_IRR,
        annot=True, fmt='.1%',
        linewidths=0.5, linecolor='white',
        cbar=True
    )
    if ax2.collections and ax2.collections[0].colorbar:
        ax2.collections[0].colorbar.formatter = mticker.PercentFormatter(1.0)
        ax2.collections[0].colorbar.update_ticks()
    ax2.set_title('Mean IRR Sensitivity: Vacancy × Interest Rate (centered at target)')
    ax2.set_xlabel('Interest Rate')
    ax2.set_ylabel('Vacancy (1 − initial occupancy)')
    plt.tight_layout()
    plt.show()

# ============== run ==============
if __name__ == "__main__":
    # Environment diagnostics
    try:
        print(f"Python interpreter: {sys.executable}")
        print(f"Matplotlib backend: {mpl.get_backend()}")
    except Exception:
        pass

    msg = "Running 10,000 simulations (seeded for reproducibility)..."
    if HAS_RICH and console:
        console.print(Panel(msg, style="cyan"))
    else:
        print(msg)

    # --- Scenario selection & execution ---
    try:
        selected = get_scenario_from_argv(DEFAULT_SCENARIO)
        scenario_list = ["Base", "Downside", "Upside"] if selected.upper() == "ALL" else [selected]
        common_params = {
            'prepay_at_sale': False,  # keep as before unless you want sale prepay
            'prepay': {
                'model': 'defeasance',
                'lockout_years': 0,
                'df_method': 'curve',
                'rf_flat_rate': 0.045,
                'rf_curve': {1: 0.042, 2: 0.043, 3: 0.044},
                'defeasance_open_year': None,
                'fees_bps': 50,
            },
        }

        last_df = None  # keep a reference if you want to use the last run later
        for scen in scenario_list:
            _print_scenario_banner(scen)
            scen_params = apply_scenario_overrides(common_params, scen)
            _debug_print_scenario(scen, scen_params) 
            df = run_simulation(
                n=10000,
                seed=44,
                parallel=False,
                params=scen_params,
            )
            if HAS_RICH and console:
                console.print(Panel(f"Completed run. Rows returned: {len(df)}", style="green"))
            else:
                print(f"Completed run. Rows returned: {len(df)}")
            analyze(df)  # show stats + IRR histogram interactively per scenario
            last_df = df
    except Exception as e:
        print("ERROR during scenario runs:\n", e)
        traceback.print_exc()
        with open("last_run_error.log", "w") as f:
            traceback.print_exc(file=f)

    # You can still call sensitivity heatmaps once after running scenarios
    try:
        print("\nGenerating 2D sensitivity tables (2 heatmaps)…")
        save_sensitivity_tables(base_params=None, sens_n=300, seed=44, output_prefix=None)
    except Exception as e:
        print("ERROR during save_sensitivity_tables():\n", e)
        traceback.print_exc()
        with open("last_run_error.log", "a") as f:
            f.write("\nERROR during save_sensitivity_tables():\n")
            traceback.print_exc(file=f)
