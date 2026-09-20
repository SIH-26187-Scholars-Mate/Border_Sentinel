"""
ai/face/face_recognizer.py

Face RECOGNITION for Border Sentinel: compare every face seen in the video
with a small gallery of enrolled reference photos and say who it is (or that
it is nobody we know).

How it works, in plain words (this is what to explain in a demo):
  1. YuNet (a small neural face detector) finds faces and their landmarks.
  2. The face is aligned using those landmarks and SFace (a neural network)
     turns it into a 128-number "embedding" — a numeric fingerprint of the face.
  3. That embedding is compared (cosine similarity) with the embeddings of the
     enrolled photos. Similarity >= threshold (0.363, OpenCV's recommended
     value for SFace) means "same person".

Gallery layout (put photos here; this folder is git-ignored on purpose):

    ai/face/known_faces/
        authorized/          people who ARE allowed here
            alice.jpg              -> identity "alice"
            bob/1.jpg, 2.jpg       -> identity "bob" (several photos = better)
        watchlist/           people who should trigger an alert when seen
            suspect_01/1.jpg

Alert rules (see FaceMatch.alert()):
  - matches a watchlist person            -> critical "watchlist match"
  - matches nobody, AND an authorized     -> high "unrecognized person"
    gallery exists
  - matches an authorized person          -> no alert
  - face too small to identify reliably   -> no alert (labelled "unverified")

Models (download once with `python -m ai.face.download_face_models`):
  ai/face/models/face_detection_yunet_2023mar.onnx
  ai/face/models/face_recognition_sface_2021dec.onnx
No extra pip packages: uses cv2.FaceDetectorYN / cv2.FaceRecognizerSF, which
ship with OpenCV >= 4.5.4 (the project pins 4.10).

Environment variables (all optional):
  FACE_RECOGNITION=off        disable recognition entirely (Haar detection only)
  FACE_KNOWN_DIR=<path>       gallery folder (default ai/face/known_faces)
  FACE_MATCH_THRESHOLD=0.363  cosine similarity needed to call two faces the same
  FACE_MIN_IDENTIFY_PX=48     faces narrower than this are not identified

Honest limits: face recognition on small, blurry or side-on CCTV faces is
unreliable. Treat an "unrecognized" alert as "a person a human should look
at", and a watchlist match as "possible match — verify", never as proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from ai.utils.config import setting
from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # x, y, w, h in ORIGINAL frame pixels

_FACE_DIR = Path(__file__).resolve().parent
DEFAULT_KNOWN_DIR = _FACE_DIR / "known_faces"
DETECTOR_MODEL = _FACE_DIR / "models" / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = _FACE_DIR / "models" / "face_recognition_sface_2021dec.onnx"

# OpenCV's documented cosine threshold for SFace (same person if score >= this).
DEFAULT_MATCH_THRESHOLD = 0.363
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_MIN_MODEL_BYTES = 100 * 1024  # a Git-LFS pointer file is only ~130 bytes

# Alert debouncing shared by the live pipeline and the recorded-video analyzer.
# An "unrecognized person" must be unrecognized in this many CONSECUTIVE
# recognition passes before we alert (one blurry frame must not raise it).
UNKNOWN_CONFIRMATIONS = 2
# Watchlist matches / unknown faces that can't be tied to a tracked person
# re-alert at most once per this many frames.
ALERT_COOLDOWN_FRAMES = 300

AUTHORIZED = "authorized"
WATCHLIST = "watchlist"
UNKNOWN = "unknown"
UNVERIFIED = "unverified"  # too small / unusable to identify


@dataclass
class FaceMatch:
    bbox: BBox
    group: str               # authorized | watchlist | unknown | unverified
    name: Optional[str]      # identity when matched, else None
    score: float             # best cosine similarity to the gallery (0 if no gallery)
    det_score: float         # face detector confidence

    @property
    def label(self) -> str:
        """Short text drawn under the face box in the live preview."""
        if self.group == AUTHORIZED:
            return f"{self.name}"
        if self.group == WATCHLIST:
            return f"WATCHLIST: {self.name}"
        if self.group == UNKNOWN:
            return "UNKNOWN"
        return "FACE"


@dataclass
class FaceAlert:
    severity: str
    confidence: float
    description: str
    kind: str  # "watchlist" | "unrecognized"


def alert_for(match: FaceMatch, has_authorized_gallery: bool) -> Optional[FaceAlert]:
    """The alert (if any) a recognised face should raise. Pure function."""
    if match.group == WATCHLIST:
        return FaceAlert(
            severity="critical",
            confidence=float(min(1.0, max(0.0, match.score))),
            description=(
                f"Watchlist match: face resembles '{match.name}' "
                f"(similarity {match.score:.2f}) — verify manually"
            ),
            kind="watchlist",
        )
    if match.group == UNKNOWN and has_authorized_gallery:
        return FaceAlert(
            severity="high",
            confidence=float(min(1.0, max(0.0, match.det_score))),
            description="Unrecognized person: face does not match any authorized person",
            kind="unrecognized",
        )
    return None


def track_for_face(face_bbox: BBox, tracked: Dict[int, tuple],
                   class_by_id: Dict[int, str]) -> Optional[int]:
    """Which tracked PERSON this face belongs to: the smallest person box that
    contains the face's centre. Lets us alert once per person, not per frame."""
    fx, fy, fw, fh = face_bbox
    cx, cy = fx + fw / 2, fy + fh / 2
    best_id, best_area = None, None
    for tid, (x1, y1, x2, y2) in tracked.items():
        if class_by_id.get(tid) != "person":
            continue
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            area = (x2 - x1) * (y2 - y1)
            if best_area is None or area < best_area:
                best_id, best_area = tid, area
    return best_id


class FaceRecognizer:
    def __init__(
        self,
        known_dir: Optional[str] = None,
        threshold: Optional[float] = None,
        detect_width: int = 640,
        det_confidence: float = 0.8,
        min_identify_px: Optional[int] = None,
        load_models: bool = True,
    ):
        self._threshold = float(threshold if threshold is not None
                                else setting("face_match_threshold", DEFAULT_MATCH_THRESHOLD))
        self._min_identify_px = int(min_identify_px if min_identify_px is not None
                                    else setting("face_min_identify_px", 48))
        self._detect_width = max(160, int(detect_width))
        self._det_confidence = float(det_confidence)
        self._known_dir = Path(known_dir or setting("face_known_dir", "") or DEFAULT_KNOWN_DIR).expanduser()

        self._detector = None
        self._recognizer = None
        self._ready = False
        # gallery: parallel lists so matching is one matrix multiply
        self._g_names: List[str] = []
        self._g_groups: List[str] = []
        self._g_feats: List[np.ndarray] = []
        self._g_matrix: Optional[np.ndarray] = None

        if str(setting("face_recognition", "on")).strip().lower() in {"off", "0", "false", "no"}:
            log.info("Face recognition disabled by FACE_RECOGNITION=off")
            return
        if load_models:
            self._load_models()
            if self._ready:
                self.load_gallery()

    # ------------------------------------------------------------------ setup
    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def has_authorized_gallery(self) -> bool:
        return AUTHORIZED in self._g_groups

    @property
    def gallery_size(self) -> int:
        return len(self._g_names)

    def _load_models(self) -> None:
        if not (hasattr(cv2, "FaceDetectorYN_create") and hasattr(cv2, "FaceRecognizerSF_create")):
            log.warning("This OpenCV build has no FaceDetectorYN/FaceRecognizerSF "
                        "(needs OpenCV >= 4.5.4); face recognition unavailable")
            return
        for path in (DETECTOR_MODEL, RECOGNIZER_MODEL):
            if not path.exists() or path.stat().st_size < _MIN_MODEL_BYTES:
                log.warning("Face model missing or incomplete: %s — run "
                            "'python -m ai.face.download_face_models'. "
                            "Falling back to detection-only (no recognition).", path)
                return
        try:
            self._detector = cv2.FaceDetectorYN_create(
                str(DETECTOR_MODEL), "", (self._detect_width, self._detect_width),
                self._det_confidence, 0.3, 5000)
            self._recognizer = cv2.FaceRecognizerSF_create(str(RECOGNIZER_MODEL), "")
            self._ready = True
            log.info("Face recognition models loaded (threshold=%.3f)", self._threshold)
        except Exception as exc:  # corrupt model, unsupported build, ...
            log.warning("Could not load face recognition models: %s", exc)

    # ---------------------------------------------------------------- gallery
    def add_identity(self, name: str, group: str, feature: np.ndarray) -> None:
        """Add one reference embedding. Several per person are fine."""
        vec = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm == 0:
            return
        self._g_names.append(name)
        self._g_groups.append(group)
        self._g_feats.append(vec / norm)
        self._g_matrix = np.vstack(self._g_feats)

    def load_gallery(self) -> None:
        """(Re)build the gallery from known_faces/{authorized,watchlist}/."""
        self._g_names, self._g_groups, self._g_feats, self._g_matrix = [], [], [], None
        for group in (AUTHORIZED, WATCHLIST):
            root = self._known_dir / group
            if not root.is_dir():
                continue
            for entry in sorted(root.iterdir()):
                if entry.is_dir():
                    name, files = entry.name, sorted(entry.iterdir())
                elif entry.suffix.lower() in _IMAGE_EXTS:
                    name, files = entry.stem, [entry]
                else:
                    continue
                added = 0
                for f in files:
                    if f.suffix.lower() not in _IMAGE_EXTS:
                        continue
                    image = cv2.imread(str(f))
                    if image is None:
                        log.warning("Could not read reference image %s", f)
                        continue
                    faces = self._detect_faces(image)
                    if not faces:
                        log.warning("No face found in reference image %s — skipped", f)
                        continue
                    # use the largest face in a reference photo
                    row = max(faces, key=lambda r: r[2] * r[3])
                    self.add_identity(name, group, self._embed_face(image, row))
                    added += 1
                if added:
                    log.info("Enrolled '%s' (%s) from %d photo(s)", name, group, added)
        log.info("Face gallery: %d embedding(s), authorized=%s",
                 self.gallery_size, self.has_authorized_gallery)

    # --------------------------------------------------------- model wrappers
    # Kept as separate methods so tests can replace them without model files.
    def _detect_faces(self, image: np.ndarray) -> List[np.ndarray]:
        """Return YuNet rows (x,y,w,h, 5 landmarks, score) in `image` pixels."""
        h, w = image.shape[:2]
        scale = min(1.0, self._detect_width / float(w))
        small = image if scale == 1.0 else cv2.resize(image, (int(w * scale), int(h * scale)),
                                                      interpolation=cv2.INTER_AREA)
        self._detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self._detector.detect(small)
        if faces is None:
            return []
        rows = []
        for row in faces:
            row = np.array(row, dtype=np.float32)
            row[:14] /= scale  # boxes + landmarks back to original pixels
            rows.append(row)
        return rows

    def _embed_face(self, image: np.ndarray, row: np.ndarray) -> np.ndarray:
        # alignCrop expects the face row as a 1x15 matrix, not a flat vector
        aligned = self._recognizer.alignCrop(image, np.asarray(row, dtype=np.float32).reshape(1, -1))
        return self._recognizer.feature(aligned)

    # --------------------------------------------------------------- matching
    def match_feature(self, feature: np.ndarray) -> Tuple[Optional[str], str, float]:
        """(name, group, best_score) for one embedding. name is None if no one
        in the gallery clears the threshold."""
        if self._g_matrix is None or not len(self._g_names):
            return None, UNKNOWN, 0.0
        vec = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm == 0:
            return None, UNKNOWN, 0.0
        sims = self._g_matrix @ (vec / norm)
        best = int(np.argmax(sims))
        score = float(sims[best])
        if score >= self._threshold:
            return self._g_names[best], self._g_groups[best], score
        return None, UNKNOWN, score

    def identify(self, frame: np.ndarray) -> List[FaceMatch]:
        """Detect every face in `frame` and identify each one."""
        if not self._ready or frame is None or getattr(frame, "size", 0) == 0:
            return []
        try:
            matches: List[FaceMatch] = []
            for row in self._detect_faces(frame):
                x, y, w, h = (int(round(v)) for v in row[:4])
                x, y = max(0, x), max(0, y)
                bbox = (x, y, w, h)
                det_score = float(row[-1])
                if w < self._min_identify_px or h < self._min_identify_px:
                    matches.append(FaceMatch(bbox, UNVERIFIED, None, 0.0, det_score))
                    continue
                name, group, score = self.match_feature(self._embed_face(frame, row))
                matches.append(FaceMatch(bbox, group, name, score, det_score))
            return matches
        except Exception as exc:
            log.warning("Face recognition failed on frame: %s", exc)
            return []
