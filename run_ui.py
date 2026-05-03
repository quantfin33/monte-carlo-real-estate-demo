#!/usr/bin/env python3
"""
RMC Model UI Launcher Script
This script launches the Streamlit UI from any directory
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).resolve().parent
    
    print("🚀 Launching RMC Monte Carlo Simulation Model...")
    print(f"📁 Directory: {script_dir}")
    print("🌐 Starting Streamlit server...")
    
    # Change to the script directory
    os.chdir(script_dir)
    
    # Check if UI.py exists
    ui_file = script_dir / "UI.py"
    if not ui_file.exists():
        print(f"❌ Error: UI.py not found at {ui_file}")
        sys.exit(1)
    
    # Launch Streamlit
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "UI.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching Streamlit: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Streamlit stopped by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
