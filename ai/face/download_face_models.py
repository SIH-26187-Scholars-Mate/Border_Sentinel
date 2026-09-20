"""
Download the two OpenCV Zoo models used for face recognition:

  * YuNet  (face detection)   face_detection_yunet_2023mar.onnx    (~0.2 MB)
  * SFace  (face embeddings)  face_recognition_sface_2021dec.onnx  (~37 MB)

Run once:   python -m ai.face.download_face_models

Both are Apache-2.0 licensed OpenCV Zoo artifacts. Use the float32 SFace
model (not the *_int8 variant, which the OpenCV Zoo has had accuracy issues
with). Each file is tried from Hugging Face first, then from the GitHub repo.
"""
from pathlib import Path
from urllib.request import Request, urlopen

MODELS_DIR = Path(__file__).resolve().parent / "models"

MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ),
}
# A Git-LFS pointer is ~130 bytes; the real files are far bigger than this.
MIN_BYTES = 100 * 1024


def _fetch(url: str, dest: Path) -> int:
    request = Request(url, headers={"User-Agent": "BorderSentinel/1.0"})
    total = 0
    with urlopen(request, timeout=120) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    return total


def download() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, urls in MODELS.items():
        dest = MODELS_DIR / name
        if dest.exists() and dest.stat().st_size >= MIN_BYTES:
            print(f"Already present: {dest}")
            continue
        for url in urls:
            print(f"Downloading {name}\n  from {url}")
            try:
                size = _fetch(url, dest)
            except Exception as exc:
                print(f"  failed: {exc}")
                dest.unlink(missing_ok=True)
                continue
            if size < MIN_BYTES:
                print(f"  got only {size} bytes (probably a Git-LFS pointer); trying next source")
                dest.unlink(missing_ok=True)
                continue
            print(f"  saved {size / (1024 * 1024):.2f} MB -> {dest}")
            break
        else:
            raise RuntimeError(f"Could not download {name} from any source")


if __name__ == "__main__":
    download()
