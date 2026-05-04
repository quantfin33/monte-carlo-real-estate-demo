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

## Enable Live AI Responses Locally

Live AI mode is optional. To enable live responses for local review, set `OPENAI_API_KEY` in your shell before launching the app:

```bash
source .venv/bin/activate
export OPENAI_API_KEY="your_key_here"
python run_ui.py
```

As a local alternative, you can place the key in `.streamlit/secrets.toml`. Never commit `.env` or `.streamlit/secrets.toml`. Without a key, the app still runs in demo analyst fallback mode.

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
