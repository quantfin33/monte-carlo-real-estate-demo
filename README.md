# RMC Monte Carlo Simulation Model

This repository contains a Streamlit-based Monte Carlo real-estate investment analytics dashboard.

Current audited readiness boundary:

- visual demo ready
- validated annual-model core
- intended for demo and local review, not for live deployment
- broader end-to-end product validation remains incomplete

Use [COMPANY_DEMO_HANDOFF.md](COMPANY_DEMO_HANDOFF.md) for the clean company-facing handoff summary, [README_UI_LAUNCH.md](README_UI_LAUNCH.md) for the local launch path, [docs/KEEWAYS_SAFE_CLAIMS.md](docs/KEEWAYS_SAFE_CLAIMS.md) for bounded external wording, and [docs/KEEWAYS_DEMO_SCRIPT.md](docs/KEEWAYS_DEMO_SCRIPT.md) for the demo flow.

## Project Overview

The app is strongest today as a visual analytics and decision-support surface for underwriting-style scenario analysis. It combines Monte Carlo simulation, annual-model output validation, sensitivity views, covenant inspection, and exportable reporting in a single local dashboard.

The current package intentionally preserves the richer UI surfaces, including Tornado, Heatmaps, Trace / Explain, and exports, while keeping claim boundaries explicit where broader validation is still incomplete.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI Layer                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │
│  │   Controls  │ │  Results    │ │   Heatmaps &        │  │
│  │   & Inputs  │ │  Display    │ │   Sensitivity       │  │
│  └─────────────┘ └─────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Simulation Engine Layer                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │
│  │  Parameter  │ │  Monte     │ │   Correlation       │  │
│  │  Validation │ │  Carlo     │ │   Engine            │  │
│  └─────────────┘ └─────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Financial Model Layer                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │
│  │  Lease Roll │ │  Debt       │ │   Exit & Tax        │  │
│  │  Logic      │ │  Modeling   │ │   Calculations      │  │
│  └─────────────┘ └─────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Core Components

### **UI.py** - Streamlit Interface
- Dynamic parameter controls with real-time validation
- Cached simulation results for performance
- Interactive heatmaps and sensitivity analysis
- Professional styling and responsive design

### **rmc_model.py** - Simulation Engine
- Monte Carlo simulation with configurable parameters
- Advanced correlation modeling (Stage 1 & Stage 2)
- Comprehensive financial metrics calculation
- Robust error handling and validation

### **Key Features**
- **Multi-scenario analysis** (Base, Downside, Upside)
- **Advanced correlation modeling** with Cholesky decomposition
- **Dynamic defeasance controls** for debt refinancing
- **Comprehensive sensitivity analysis** with 2D heatmaps
- **Professional reporting** with detailed metrics

## Quick Start

### Prerequisites
- Python 3.11+
- A local virtual environment
- Runtime dependencies installed from `requirements.txt`

### Installation
```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install runtime dependencies
python -m pip install -r requirements.txt

# Run the canonical launcher
python run_ui.py
```

### Usage
1. **Configure Parameters**: Set your real estate investment parameters
2. **Run Simulations**: Execute Monte Carlo simulations with configurable sample sizes
3. **Analyze Results**: View IRR distributions, sensitivity heatmaps, and detailed metrics
4. **Export Data**: Download results for further analysis

## Company Handoff Notes

For portfolio or company handoff, use these files in this order:

- [COMPANY_DEMO_HANDOFF.md](COMPANY_DEMO_HANDOFF.md)
- [README_UI_LAUNCH.md](README_UI_LAUNCH.md)
- [docs/KEEWAYS_SAFE_CLAIMS.md](docs/KEEWAYS_SAFE_CLAIMS.md)
- [docs/KEEWAYS_DEMO_SCRIPT.md](docs/KEEWAYS_DEMO_SCRIPT.md)

Do not describe this repository as ready for live deployment, as a fully complete underwriting platform, or as a system with live business-platform or agent-tool connections already shipped.

## 📊 Key Metrics Calculated

- **IRR (Internal Rate of Return)**
- **NPV (Net Present Value)**
- **Cash-on-Cash Return**
- **Equity Multiple**
- **DSCR (Debt Service Coverage Ratio)**
- **LTV (Loan-to-Value)**
- **Break-even Occupancy**

## 🔬 Advanced Features

### **Correlation Modeling**
- **Stage 1**: Latent market strength (occupancy ↔ rent growth)
- **Stage 2**: Generalized correlation engine for multiple variables
- **Cholesky decomposition** for mathematically valid correlations

### **Sensitivity Analysis**
- **2D Heatmaps**: Exit cap rate × Rent growth, Vacancy × Interest rate
- **Parameter ranges**: Configurable for your specific analysis needs
- **Cached results**: Fast iteration and analysis

### **Defeasance Controls**
- **Flat vs. Curve** discount methods
- **Risk-free rate** configuration
- **Fee structure** modeling
- **Lockout periods** and refinancing constraints

## 📈 Performance Characteristics

- **Simulation Speed**: 10,000 runs in ~30 seconds (M1 Mac)
- **Memory Usage**: Efficient pandas operations with minimal overhead
- **Scalability**: Linear scaling with simulation count
- **Caching**: Streamlit caching for repeated calculations

## Package Structure

```text
monte-carlo-demo-package/
├── README.md
├── README_UI_LAUNCH.md
├── COMPANY_DEMO_HANDOFF.md
├── UI.py
├── rmc_model.py
├── engine_output_contract.py
├── trace_tools.py
├── ui_metrics.py
├── metrics_schema.py
├── metrics_utils.py
├── metrics_registry.py
├── run_ui.py
├── run_ui.sh
├── run.sh
├── run_tests.py
├── pyproject.toml
├── requirements.txt
├── requirements_testing.txt
├── docs/
├── tests/
├── screenshots/
└── artifacts/
```

## Testing
```bash
# Install test dependencies
python -m pip install -r requirements_testing.txt

# Run the smoke check
python run_tests.py smoke

# Run a targeted UI defaults test
python -m pytest tests/test_ui_session_defaults.py -q -o addopts=''

# Run targeted core model tests
python -m pytest tests/test_core_model.py -q -o addopts=''

# Run the included advanced metrics test file
python -m pytest tests/test_metrics_full.py -q -o addopts=''
```

## Documentation

- [docs/KEEWAYS_SAFE_CLAIMS.md](docs/KEEWAYS_SAFE_CLAIMS.md)
- [docs/KEEWAYS_DEMO_SCRIPT.md](docs/KEEWAYS_DEMO_SCRIPT.md)
- [docs/KEEWAYS_POSITIONING_MEMO.md](docs/KEEWAYS_POSITIONING_MEMO.md)
- [docs/metrics_contract.md](docs/metrics_contract.md)
- [docs/metric_inputs_map.md](docs/metric_inputs_map.md)
- [docs/adr/0001_domain_invariants.md](docs/adr/0001_domain_invariants.md)

## Screenshots

- [screenshots/keeways-review-home.png](screenshots/keeways-review-home.png)
- [screenshots/keeways-review-home-after-load.png](screenshots/keeways-review-home-after-load.png)
- [screenshots/keeways-review-after-run.png](screenshots/keeways-review-after-run.png)

## 🎯 Roadmap

- [ ] **Performance Optimization**: GPU acceleration for large simulations
- [ ] **Advanced Correlations**: Machine learning-based correlation detection
- [ ] **Cloud Deployment**: AWS/Azure deployment options
- [ ] **API Layer**: REST API for integration with other tools
- [ ] **Mobile Support**: Responsive design for mobile devices

## Future Workflow Direction

This dashboard is also a candidate for a later workflow layer that could expose simulation, metrics, risk summary, trace, and reporting flows to assistants or adjacent business systems. This is a forward-looking direction only; the current package does not include a shipped agent-tool layer or live business-system connectivity.

- Keep the existing Streamlit experience and financial model as the source of truth.
- Add a thin structured tool layer around simulation runs, metric retrieval, trace/explain flows, and export generation.
- Return structured outputs so an assistant can compare scenarios, summarize risk, and generate repeatable client-facing deliverables.
- Treat broader business-system handoff as a later phase, not a current capability.

## Keeways Readiness Notes

The current Keeways packaging pass keeps the richer UI surfaces visible and uses guarded placeholders, captions, and validation-state messaging instead of deleting advanced sections. For the sendable package, rely on:

- [docs/KEEWAYS_SAFE_CLAIMS.md](docs/KEEWAYS_SAFE_CLAIMS.md)
- [docs/KEEWAYS_POSITIONING_MEMO.md](docs/KEEWAYS_POSITIONING_MEMO.md)
- [docs/KEEWAYS_DEMO_SCRIPT.md](docs/KEEWAYS_DEMO_SCRIPT.md)

For external Keeways-facing wording, treat occupancy-sensitive advanced metrics and any placeholder-backed preserved surfaces as under verification unless the safe-claims note says otherwise.

---

**Built with ❤️ for real estate professionals who demand precision and insight.**
