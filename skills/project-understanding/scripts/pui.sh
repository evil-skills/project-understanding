#!/usr/bin/env bash
# PUI Shell Shim - Cross-platform entry point for Unix-like systems
# Usage: ./scripts/pui [command] [options]

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

# Define Venv locations
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
GLOBAL_PUI_DIR="$XDG_DATA_HOME/pui"
GLOBAL_VENV="$GLOBAL_PUI_DIR/venv"
LOCAL_VENV="$SKILL_ROOT/venv"

# Find Python executable
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo "Error: Python not found. Please install Python 3.10+" >&2
        exit 1
    fi
}

PYTHON=$(find_python)

# Auto-bootstrap if needed
bootstrap_if_needed() {
    local TARGET_VENV=""
    
    # Check if global venv exists and is healthy
    if [ -d "$GLOBAL_VENV" ] && [ -f "$GLOBAL_VENV/bin/python" ]; then
        TARGET_VENV="$GLOBAL_VENV"
    # Check if local venv exists and is healthy
    elif [ -d "$LOCAL_VENV" ] && [ -f "$LOCAL_VENV/bin/python" ]; then
        TARGET_VENV="$LOCAL_VENV"
    else
        # Try to create global venv
        echo "Bootstrap: Setting up Project Understanding Skill..."
        if mkdir -p "$GLOBAL_PUI_DIR" 2>/dev/null; then
            TARGET_VENV="$GLOBAL_VENV"
        else
            echo "Bootstrap: Global directory $GLOBAL_PUI_DIR not writable, falling back to local venv."
            TARGET_VENV="$LOCAL_VENV"
        fi
        
        # Run bootstrap script
        "$PYTHON" "$SCRIPT_DIR/bootstrap.py" --non-interactive --target-dir "$TARGET_VENV"
    fi
    
    echo "$TARGET_VENV"
}

# Get healthy venv path
VENV_PATH=$(bootstrap_if_needed)

# Activate venv
# shellcheck source=/dev/null
source "$VENV_PATH/bin/activate"

# Set PYTHONPATH to include skill root for module imports
export PYTHONPATH="$SKILL_ROOT:$PYTHONPATH"

# Run PUI
exec python3 "$SCRIPT_DIR/pui.py" "$@"
