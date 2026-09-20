"""
ai/anpr/ocr.py
Runs OCR on a cropped plate region.

Requires the system Tesseract binary to be installed separately — this is
NOT a pip package that bundles it:
  Ubuntu/Debian: sudo apt install tesseract-ocr
  macOS:         brew install tesseract
  Windows:       https://github.com/UB-Mannheim/tesseract/wiki

pytesseract (the pip package) is just a thin wrapper that shells out to
that binary — without it installed, read_plate() will raise clearly rather
than silently returning garbage.
"""
import re

import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)

# Plates are typically uppercase letters + digits only — strip anything else
# out of the raw OCR output.
_ALLOWED_CHARS = re.compile(r"[^A-Z0-9]")


def read_plate(plate_crop: np.ndarray) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed — add it to ai/requirements.txt"
        ) from exc

    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    try:
        raw_text = pytesseract.image_to_string(
            thresh, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
    except Exception as exc:  # pytesseract raises TesseractNotFoundError if the
        # binary itself isn't installed — surface that clearly instead of a
        # confusing stack trace deep in a third-party library.
        raise RuntimeError(
            "OCR failed — is the Tesseract binary installed on this system? "
            f"Original error: {exc}"
        ) from exc

    cleaned = _ALLOWED_CHARS.sub("", raw_text.upper().strip())
    return cleaned
