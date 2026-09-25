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

if [ ! -d .venv ]; then
  echo "== creating venv =="
  python3 -m venv .venv
fi
PY=.venv/bin/python

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
