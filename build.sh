#!/usr/bin/env bash
# Build Card-Sharp .app locally from source.
# Requires: a macOS framework Python (python.org preferred) — NOT miniconda.
#
# Usage:
#   ./build.sh            # build .app in dist/
#   ./build.sh clean      # remove build/dist artifacts

set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="Card-Sharp"
# Prefer python.org's framework Python (bundles the mature Tcl/Tk 8.6.x).
# Homebrew's python-tk formula can silently ship Tk 9.0.x, whose
# early-release Cocoa backend drops single clicks on native window-chrome
# controls (minimize button, title bar) — see tk-macos-common-mistakes
# section 5.
BREW_PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
[ -x "$BREW_PY" ] || BREW_PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
[ -x "$BREW_PY" ] || BREW_PY="/usr/local/opt/python@3.14/bin/python3.14"
[ -x "$BREW_PY" ] || BREW_PY="/opt/homebrew/opt/python@3.14/bin/python3.14"
[ -x "$BREW_PY" ] || BREW_PY="$(command -v python3)"

if [[ "${1:-}" == "clean" ]]; then
  rm -rf build dist venv .eggs *.egg-info
  echo "Cleaned."
  exit 0
fi

echo ">> Python: $BREW_PY ($($BREW_PY --version))"
if $BREW_PY -c "import sys; sys.exit(0 if 'conda' not in sys.prefix.lower() else 1)"; then
  :
else
  echo "!! Refusing to build with conda Python (py2app breaks). Install a python.org framework Python."
  exit 1
fi

echo ">> Creating venv"
$BREW_PY -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip wheel setuptools >/dev/null
python -m pip install -r requirements.txt >/dev/null

echo ">> Regenerating icon"
python assets/make_icon.py

echo ">> Running self-tests"
python -m card_sharp.self_test

echo ">> Building .app with py2app"
rm -rf build dist
python setup.py py2app

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "!! Build failed: $APP_PATH not found"
  exit 1
fi

echo ">> Checking portability (otool -L on main binary)"
MAIN_BIN="$APP_PATH/Contents/MacOS/main"
[ -x "$MAIN_BIN" ] || MAIN_BIN="$APP_PATH/Contents/MacOS/${APP_NAME}"
if [[ -x "$MAIN_BIN" ]]; then
  otool -L "$MAIN_BIN" | sed -n '1,30p'
fi

ZIP_PATH="dist/${APP_NAME}.zip"
echo ">> Creating portable app zip"
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
unzip -t "$ZIP_PATH" >/dev/null

echo ""
echo "Built: $APP_PATH"
echo "Zip:   $ZIP_PATH"
echo "Launch:  open '$APP_PATH'"
