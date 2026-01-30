#!/usr/bin/env bash
# PUI Shell Shim - Cross-platform entry point for Unix-like systems
# Usage: ./scripts/pui [command] [options]

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Find Python executable
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo "Error: Python not found. Please install Python 3.9+" >&2
        exit 1
    fi
}

PYTHON=$(find_python)

# Check Python version
PYTHON_VERSION=$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo "Error: Python 3.9+ required, found $PYTHON_VERSION" >&2
    exit 1
fi

# Set up environment
export PUI_SCRIPT_DIR="$SCRIPT_DIR"
export PUI_PARENT_DIR="$PARENT_DIR"

# Check for virtual environment
if [ -d "$PARENT_DIR/.venv" ]; then
    # shellcheck source=/dev/null
    source "$PARENT_DIR/.venv/bin/activate"
elif [ -d "$PARENT_DIR/venv" ]; then
    # shellcheck source=/dev/null
    source "$PARENT_DIR/venv/bin/activate"
fi

# Run PUI
exec $PYTHON -m scripts.pui "$@"
