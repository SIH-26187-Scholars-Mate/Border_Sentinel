"""
Download the Indian YOLOv8 number-plate detector used by the ANPR experiment.

This is deliberately separate from the production ANPR pipeline.  The model
is downloaded only when the developer explicitly runs this script.
"""
from pathlib import Path
from urllib.request import Request, urlopen

MODEL_URL = (
    "https://raw.githubusercontent.com/lavanyashree2805/"
    "yolov8-license-plate-india/main/"
    "yolov8_plate_detect/model_weights/Lavanya_NamePlateModel.pt"
)
MODEL_PATH = Path(__file__).resolve().parent / "models" / "Lavanya_NamePlateModel.pt"


def download() -> Path:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading Indian YOLOv8 plate detector...")
    print(f"Source: {MODEL_URL}")
    print(f"Destination: {MODEL_PATH}")

    request = Request(MODEL_URL, headers={"User-Agent": "BorderSentinel/1.0"})
    with urlopen(request, timeout=60) as response, MODEL_PATH.open("wb") as output:
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            total += len(chunk)

    # A Git-LFS pointer is only a few hundred bytes. A real .pt file should
    # be much larger, so fail loudly rather than leaving a broken model file.
    if total < 1024 * 1024:
        MODEL_PATH.unlink(missing_ok=True)
        raise RuntimeError(
            "Downloaded file is unexpectedly small. GitHub may have returned "
            "a Git-LFS pointer instead of the model weights."
        )

    print(f"Downloaded {total / (1024 * 1024):.2f} MB")
    return MODEL_PATH


if __name__ == "__main__":
    download()
