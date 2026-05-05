# RMC Monte Carlo UI Launch Guide

## Download / Clone The Project

Clone with Git:

```bash
git clone https://github.com/quantfin33/monte-carlo-real-estate-demo.git
cd monte-carlo-real-estate-demo
```

Or download a ZIP from GitHub:

1. Open the repository link.
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Unzip the folder.
5. Open Terminal inside the unzipped project folder.

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

By default, the app runs in demo analyst fallback mode without an API key. Live AI mode is optional and currently uses shell environment variables.

To test live AI responses locally, install the optional OpenAI SDK and set `OPENAI_API_KEY` before launching the app:

```bash
source .venv/bin/activate
python -m pip install openai
export OPENAI_API_KEY="your_key_here"
# optional
export OPENAI_MODEL="gpt-5-mini"
python run_ui.py
```

If the OpenAI SDK is not installed or no API key is configured, the AI Analyst remains in fallback/demo mode. Never commit local secret files such as `.env` or `.streamlit/secrets.toml`. This project is a portfolio demo, not investment advice or production financial software.

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
