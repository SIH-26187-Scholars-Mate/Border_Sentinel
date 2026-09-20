# CPU-only base — swap for a CUDA base image (e.g. nvidia/cuda) if you have
# a GPU available and want real-time inference throughput; CPU is fine for
# a prototype validating the pipeline logic.
FROM python:3.11-slim

# libgl1 + libglib2.0-0 are required by opencv-python-headless at runtime;
# tesseract-ocr is required for ai/anpr/ocr.py to work at all.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ai/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ai/ ./ai/

CMD ["python", "-m", "ai.main", "--camera-id", "REPLACE_ME"]
