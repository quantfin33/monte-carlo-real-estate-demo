# RMC Monte Carlo UI Launch Guide

## Quick Start

Use the verified local environment and the canonical launcher:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_ui.py
```

When Streamlit starts, open the local URL printed in the terminal.

## Recommended Launch Commands

Canonical launcher:

```bash
source .venv/bin/activate
python run_ui.py
```

Shell wrapper:

```bash
./run_ui.sh
```

Smoke check:

```bash
source .venv/bin/activate
python -m pip install -r requirements_testing.txt
python run_tests.py smoke
```

## Troubleshooting

### UI.py not found

Cause: the app is being launched from the wrong directory or without the project launcher.

Use:

```bash
source .venv/bin/activate
python run_ui.py
```

### Streamlit module missing

Cause: runtime dependencies are not installed in the current virtual environment.

Use:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_ui.py
```

## Best Practice

Treat `run_ui.py` as the canonical launcher for demos and local validation. Avoid using bare `streamlit run UI.py` before the environment is set up.
