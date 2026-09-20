"""
Standalone CPU experiment for the Indian YOLOv8 number-plate detector.

IMPORTANT:
- This file does NOT replace the current contour-based ANPR detector.
- It is intentionally isolated so the working Border Sentinel pipeline is
  untouched while we compare plate localization quality and CPU speed.

Pipeline:
    camera/video/image
        -> existing YOLOv8n vehicle detector
        -> vehicle crop
        -> Indian YOLOv8 plate detector
        -> plate bounding box

Example from project root:
    python -m ai.anpr.download_plate_model
    python -m ai.anpr.test_yolo_plate --source 0

Force CPU is intentional. This is the deployment test we care about.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

DEFAULT_PLATE_MODEL = (
    Path(__file__).resolve().parent / "models" / "Lavanya_NamePlateModel.pt"
)

VEHICLE_CLASS_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck in COCO
VEHICLE_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def load_models(vehicle_model_path: str, plate_model_path: Path):
    from ultralytics import YOLO

    print("Loading vehicle detector on CPU...")
    vehicle_model = YOLO(vehicle_model_path)
    print("Loading Indian plate detector on CPU...")
    plate_model = YOLO(str(plate_model_path))
    return vehicle_model, plate_model


def parse_source(value: str):
    return int(value) if value.isdigit() else value


def draw_label(frame, text: str, x: int, y: int):
    y = max(22, y)
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )


def process_frame(
    frame: np.ndarray,
    vehicle_model,
    plate_model,
    vehicle_conf: float,
    plate_conf: float,
    imgsz: int,
):
    start = time.perf_counter()

    vehicle_result = vehicle_model.predict(
        source=frame,
        conf=vehicle_conf,
        classes=list(VEHICLE_CLASS_IDS),
        imgsz=imgsz,
        device="cpu",
        verbose=False,
    )[0]

    vehicle_ms = (time.perf_counter() - start) * 1000
    plate_ms = 0.0
    vehicle_count = 0
    plate_count = 0

    for box in vehicle_result.boxes:
        cls_id = int(box.cls[0])
        if cls_id not in VEHICLE_CLASS_IDS:
            continue

        vehicle_count += 1
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            continue

        plate_start = time.perf_counter()
        plate_result = plate_model.predict(
            source=vehicle_crop,
            conf=plate_conf,
            imgsz=imgsz,
            device="cpu",
            verbose=False,
        )[0]
        plate_ms += (time.perf_counter() - plate_start) * 1000

        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
        draw_label(
            frame,
            f"{VEHICLE_NAMES.get(cls_id, 'vehicle')} {confidence:.2f}",
            x1,
            y1 - 4,
        )

        # Plate model has one class, so every returned box is a plate.
        for plate_box in plate_result.boxes:
            pconf = float(plate_box.conf[0])
            px1, py1, px2, py2 = [int(v) for v in plate_box.xyxy[0].tolist()]
            px1, py1 = max(0, px1), max(0, py1)
            px2, py2 = min(vehicle_crop.shape[1], px2), min(vehicle_crop.shape[0], py2)
            if px2 <= px1 or py2 <= py1:
                continue

            plate_count += 1
            gx1, gy1 = x1 + px1, y1 + py1
            gx2, gy2 = x1 + px2, y1 + py2
            cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (0, 255, 0), 2)
            draw_label(frame, f"plate {pconf:.2f}", gx1, gy1 - 4)

    total_ms = (time.perf_counter() - start) * 1000
    return frame, vehicle_count, plate_count, vehicle_ms, plate_ms, total_ms


def run_image(source, vehicle_model, plate_model, args):
    frame = cv2.imread(str(source))
    if frame is None:
        raise RuntimeError(f"Could not read image: {source}")

    result, vehicles, plates, vehicle_ms, plate_ms, total_ms = process_frame(
        frame, vehicle_model, plate_model, args.vehicle_conf, args.plate_conf, args.imgsz
    )

    output = Path(args.output or "runtime/anpr-yolo-test.jpg")
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), result)

    print("\n=== CPU PLATE DETECTOR RESULT ===")
    print(f"Vehicles: {vehicles}")
    print(f"Plates:   {plates}")
    print(f"Vehicle model: {vehicle_ms:.1f} ms")
    print(f"Plate model:   {plate_ms:.1f} ms")
    print(f"Total:         {total_ms:.1f} ms")
    print(f"Output: {output}")


def run_stream(source, vehicle_model, plate_model, args):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source: {source}")

    output_path = Path(args.output) if args.output else None
    writer = None
    frames = 0
    total_time = 0.0
    total_vehicles = 0
    total_plates = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            result, vehicles, plates, _, _, total_ms = process_frame(
                frame, vehicle_model, plate_model, args.vehicle_conf, args.plate_conf, args.imgsz
            )
            frames += 1
            total_time += total_ms
            total_vehicles += vehicles
            total_plates += plates

            fps = 1000.0 / total_ms if total_ms > 0 else 0.0
            cv2.putText(
                result,
                f"CPU | {fps:.1f} FPS | vehicles {vehicles} | plates {plates}",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            if writer is None and output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                height, width = result.shape[:2]
                fps_in = cap.get(cv2.CAP_PROP_FPS)
                if not fps_in or fps_in <= 0:
                    fps_in = 20.0
                writer = cv2.VideoWriter(
                    str(output_path),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    fps_in,
                    (width, height),
                )
            if writer:
                writer.write(result)

            if not args.no_display:
                cv2.imshow("Border Sentinel - Indian YOLOv8 Plate Test (CPU)", result)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

            if args.frames and frames >= args.frames:
                break
    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()

    print("\n=== CPU PLATE DETECTOR BENCHMARK ===")
    print(f"Frames processed: {frames}")
    print(f"Vehicles found:   {total_vehicles}")
    print(f"Plates found:     {total_plates}")
    if frames:
        avg_ms = total_time / frames
        print(f"Average/frame:    {avg_ms:.1f} ms")
        print(f"Approx FPS:       {1000.0 / avg_ms:.2f}")
    if output_path:
        print(f"Output: {output_path}")


def build_parser():
    parser = argparse.ArgumentParser(description="CPU-only Indian YOLOv8 plate detector test")
    parser.add_argument("--source", default="0", help="Webcam index, video path, or image path")
    parser.add_argument("--model", default="yolov8n.pt", help="Vehicle detector weights")
    parser.add_argument("--plate-model", default=str(DEFAULT_PLATE_MODEL), help="Plate detector weights")
    parser.add_argument("--vehicle-conf", type=float, default=0.45)
    parser.add_argument("--plate-conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--frames", type=int, default=0, help="Stop after N frames; 0 means until stopped")
    parser.add_argument("--output", default="", help="Optional output image/video path")
    parser.add_argument("--no-display", action="store_true", help="Run benchmark without opening a window")
    return parser


def main():
    args = build_parser().parse_args()
    plate_model_path = Path(args.plate_model)
    if not plate_model_path.exists():
        raise FileNotFoundError(
            f"Plate model not found: {plate_model_path}\n"
            "Run first: python -m ai.anpr.download_plate_model"
        )

    vehicle_model, plate_model = load_models(args.model, plate_model_path)
    source = parse_source(args.source)

    if isinstance(source, str) and Path(source).suffix.lower() in {
        ".jpg", ".jpeg", ".png", ".bmp", ".webp"
    }:
        run_image(source, vehicle_model, plate_model, args)
    else:
        run_stream(source, vehicle_model, plate_model, args)


if __name__ == "__main__":
    main()
