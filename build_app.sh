#!/usr/bin/env bash
# Build the SPARTA DSMC GUI desktop app.
# Usage: ./build_app.sh

set -e
cd "$(dirname "$0")"

echo "=== Installing / verifying dependencies ==="
pip install --quiet PySide6 pyinstaller

echo "=== Running PyInstaller ==="
pyinstaller sparta_gui.spec --clean --noconfirm

echo ""
echo "=== Build complete ==="
if [[ "$(uname)" == "Darwin" ]]; then
    echo "App bundle: dist/SPARTA DSMC Setup.app"
    echo "To run:     open 'dist/SPARTA DSMC Setup.app'"
else
    echo "Executable: dist/SPARTA DSMC Setup/"
fi
