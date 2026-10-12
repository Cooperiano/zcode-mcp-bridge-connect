#!/usr/bin/env bash
set -euo pipefail

# Local bootstrap only; never installs or authenticates a model provider.
cd "$(dirname "$0")"
if [[ $# -gt 1 || (${1:-} != "" && ${1:-} != "--test") ]]; then
  echo "Usage: ./setup.sh [--test]" >&2
  exit 2
fi
bridge_python="${PYTHON:-python3}"
command -v "$bridge_python" >/dev/null 2>&1 || { echo "Error: Python 3.11+ is required (set PYTHON to its executable)." >&2; exit 1; }
"$bridge_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Error: Python 3.11+ is required.")'
echo "Checking Python sources (standard library only)..."
"$bridge_python" -m compileall -q .
if [[ ${1:-} == "--test" ]]; then
  echo "Running offline fixture tests..."
  "$bridge_python" -m unittest discover -s tests -p 'test_*.py'
fi
echo "Setup complete. Register server.py in your MCP client using the README template."
echo "Keep your existing ZCode installation and login on this device."
echo "See AGENTS.md for development commands."
