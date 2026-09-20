#!/usr/bin/env bash
# One combined venv for backend/ + ai/. Run once from the project root:
#   ./setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "Border Sentinel backend + AI dependencies are installed in .venv."
echo
echo "Start the backend (from the backend/ folder, using this venv):"
echo "  source .venv/bin/activate  # if not already active"
echo "  cd backend && uvicorn app.main:app --reload"
echo
echo "Tesseract is also required for OCR/ANPR — install it separately if you haven't:"
echo "  sudo apt install tesseract-ocr   # Debian/Ubuntu"
echo "  brew install tesseract           # macOS"
