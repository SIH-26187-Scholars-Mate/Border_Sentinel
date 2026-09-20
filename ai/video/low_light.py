"""
ai/video/low_light.py

Software "night vision" — a preprocessing step that brightens dim frames
before they reach the detector. This does NOT recover detail from complete
darkness (no light hitting the sensor = nothing to pull out); it's for
underexposed/dim scenes, which is what a claim like "AI night vision"
realistically means without an IR illuminator.

Pipeline: measure brightness -> only touch genuinely dim frames -> gamma
correction (brighten shadows without blowing out highlights) -> CLAHE
(local contrast, so the brightened image isn't flat/washed out) -> a light
denoise pass (brightening amplifies sensor noise along with the signal).

Deliberately skips well-lit frames entirely — brightening an already-bright
frame just introduces noise and washout for no benefit, so a brightness gate
keeps normal daytime footage untouched.
"""
import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)


def _mean_brightness(frame: np.ndarray) -> float:
    return float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())


def _gamma_correct(frame: np.ndarray, gamma: float) -> np.ndarray:
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(frame, table)


def _clahe(frame: np.ndarray, clip_limit: float = 2.5) -> np.ndarray:
    # Apply on the L channel in LAB space so color isn't distorted —
    # equalizing each BGR channel separately washes colors out.
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def enhance_low_light(
    frame: np.ndarray,
    brightness_threshold: float = 90.0,
    gamma: float = 1.8,
    denoise: bool = True,
) -> np.ndarray:
    """Brightens `frame` if (and only if) it's genuinely dim. Returns the
    original frame untouched otherwise, so normal daylight footage never
    gets needlessly reprocessed."""
    brightness = _mean_brightness(frame)
    if brightness >= brightness_threshold:
        return frame

    enhanced = _gamma_correct(frame, gamma)
    enhanced = _clahe(enhanced)
    if denoise:
        # h=7 is a mild strength — enough to clean up gamma-amplified sensor
        # noise without smearing away real detail YOLO needs to detect on.
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, h=7, hColor=7,
                                                     templateWindowSize=7, searchWindowSize=21)
    log.debug("Low-light enhancement applied (brightness=%.1f -> threshold=%.1f)",
              brightness, brightness_threshold)
    return enhanced
