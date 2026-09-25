#!/usr/bin/env bash
# One-command bootstrap for the CaptionX extraction environment.
#
#   ./setup.sh
#
# Creates .venv, installs the pinned Python stack (with the headless-OpenCV
# fix for servers without libGL), installs dev tools, and fetches the sample
# NCERT fixtures. OCR models are vendored in models/official_models/ (no
# network needed for inference).
set -euo pipefail

cd "$(dirname "$0")"

# paddlepaddle's pinned wheels exist only for CPython 3.9-3.13 (PyPI), so on
# a brand-new default python3 (e.g. 3.14) pip silently resolves to nothing
# and dies with "No matching distribution found". Pick a compatible
# interpreter explicitly; reuse the venv only when ITS interpreter is
# compatible too.
SUPPORTED_PY="3.9 3.10 3.11 3.12 3.13"

py_version() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
py_supported() {
  local v; v="$(py_version "$1")" || return 1
  for s in $SUPPORTED_PY; do [ "$v" = "$s" ] && return 0; done
  return 1
}

if [ -x .venv/bin/python ] && py_supported .venv/bin/python; then
  PY=.venv/bin/python                      # healthy, compatible venv — fast path
else
  PYBIN=""
  for cand in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    command -v "$cand" >/dev/null 2>&1 && py_supported "$cand" && { PYBIN="$cand"; break; }
  done
  if [ -z "$PYBIN" ]; then
    # Escape hatch for distros that ship only an unsupported Python (e.g.
    # Debian/Ubuntu releases with 3.14 as the sole python3 — their apt has
    # no python3.11 package either): uv fetches a standalone CPython without
    # sudo. Everything downstream works unchanged.
    if command -v uv >/dev/null 2>&1; then
      echo "== no compatible system Python — fetching 3.11 via uv =="
      uv python install 3.11 \
        || { echo "ERROR: uv could not fetch Python 3.11."; exit 1; }
      uv venv --python 3.11 --clear .venv \
        || { echo "ERROR: 'uv venv --python 3.11' failed."; exit 1; }
      PY=.venv/bin/python
    else
      echo "ERROR: the pinned paddlepaddle ships wheels only for CPython ${SUPPORTED_PY}."
      echo "Your default python3 is $(py_version python3 2>/dev/null || echo unknown) and no compatible interpreter was found."
      echo "Pick ONE of:"
      echo "  no sudo:  curl -LsSf https://astral.sh/uv/install.sh | sh   # then re-run ./setup.sh"
      echo "  Ubuntu LTS: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.11 python3.11-venv"
      echo "  macOS:      brew install python@3.11"
      echo "  any OS:     pyenv install 3.11 && pyenv local 3.11"
      exit 1
    fi
  else
    echo "== creating venv (fresh, $PYBIN $(py_version "$PYBIN")) =="
    "$PYBIN" -m venv --clear .venv \
      || { echo "ERROR: '$PYBIN -m venv' failed."
           echo "On Debian/Ubuntu: sudo apt install python3-venv python3-pip"
           exit 1; }
    PY=.venv/bin/python
  fi
fi

# A venv without a working pip dies at the first pip call (interrupted run,
# or a distro venv built without ensurepip) — bootstrap explicitly.
if [ ! -x .venv/bin/pip ]; then
  "$PY" -m ensurepip --upgrade >/dev/null 2>&1 \
    || { echo "ERROR: .venv has no pip and ensurepip is unavailable."
         echo "On Debian/Ubuntu: sudo apt install python3-venv python3-pip"
         exit 1; }
  "$PY" -m pip install --upgrade pip -q
fi

echo "== installing pinned stack (requirements.txt) =="
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt

echo "== installing dev tools (requirements-dev.txt) =="
.venv/bin/pip install -r requirements-dev.txt

echo "== headless OpenCV fix (servers without libGL) =="
# paddleocr/paddlex depend on opencv-contrib-python by dist name; the headless
# wheel provides the actual `import cv2` so both checks stay satisfied.
.venv/bin/pip uninstall -y -q opencv-contrib-python opencv-contrib-python-headless || true
.venv/bin/pip install -q --no-deps --force-reinstall opencv-contrib-python==4.10.0.84
# headless must be installed LAST — it owns the actual cv2/ files:
.venv/bin/pip install -q --no-deps --force-reinstall opencv-contrib-python-headless==4.10.0.84

echo "== fetching sample NCERT fixtures (not committed) =="
./fixtures/download.sh

echo "== verifying =="
"$PY" -c "import cv2, paddle, paddleocr, pymupdf; print('cv2', cv2.__version__, '| paddle', paddle.__version__, '| pymupdf', pymupdf.pymupdf_version)"
"$PY" -m pytest tests -q

echo
echo "Done. OCR models are vendored under models/official_models/."
echo "Try: .venv/bin/python scripts/verify_ocr.py --page 1"
