#!/bin/bash

# RMC Model UI Launcher Script
# This script launches the Streamlit UI from any directory

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

echo "🚀 Launching RMC Monte Carlo Simulation Model..."
echo "📁 Directory: $SCRIPT_DIR"
echo "🌐 Starting Streamlit server..."

# Change to the script directory and delegate to the canonical Python launcher
cd "$SCRIPT_DIR"
exec "$PYTHON_BIN" run_ui.py
