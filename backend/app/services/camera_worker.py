"""Manage one AI worker process per configured camera.

The backend owns the lifecycle: saving a camera starts its AI worker, updating
its RTSP source restarts it, and deleting/deactivating a camera stops it.
Workers are normal child processes running ``python -m ai.main``; the backend
never shells out through a terminal and arguments are passed as an argv list.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import RLock
from typing import Optional
from uuid import UUID

from app.core.config import get_settings
import logging

log = logging.getLogger(__name__)

_PR_SET_PDEATHSIG = 1


def _die_with_parent():
    """Runs inside the child right after fork(), before exec().

    Asks the kernel to SIGTERM this child the moment its parent (the
    backend process) dies for ANY reason — clean shutdown, crash,
    `--reload` force-killing the old process, `kill -9`, etc. Without
    this, a child that survives a backend restart becomes an orphan
    that keeps the webcam device (and its preview port) locked, which
    is exactly what caused "camera won't start" and "webcam still on
    after logout": the *new* backend process has no record of it and
    can never stop it. Linux-only; harmless no-op path on other OSes.
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(_PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        # Best-effort safety net only — never block worker startup on it.
        pass


class CameraWorkerManager:
    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = RLock()
        self._root = Path(__file__).resolve().parents[3]
        self._log_dir = self._root / "runtime" / "ai-logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._last_errors: dict[str, str] = {}

    def _preview_port(self, camera_number: int) -> int:
        return get_settings().ai_preview_base_port + int(camera_number)

    def _source(self, stream_url: Optional[str]) -> str:
        # Blank/null source intentionally means the local laptop webcam.
        # Accept the literal strings users commonly enter for an empty field.
        value = (stream_url or "").strip()
        if not value or value.lower() in {"null", "none", "webcam", "camera"}:
            return "0"
        return value

    def _python_executable(self) -> str:
        """Find a Python environment that can run the AI package.

        The backend and AI are intentionally launched as a child process, but
        they must use an environment containing OpenCV/Ultralytics. Prefer an
        explicit BORDER_SENTINEL_AI_PYTHON, then the project's AI/backend venvs,
        and finally the interpreter running FastAPI.
        """
        explicit = os.environ.get("BORDER_SENTINEL_AI_PYTHON")
        candidates = []
        if explicit:
            candidates.append(Path(explicit))
        if os.name == "nt":
            candidates += [
                self._root / "ai" / ".venv" / "Scripts" / "python.exe",
                self._root / ".venv" / "Scripts" / "python.exe",
                self._root / "backend" / ".venv" / "Scripts" / "python.exe",
            ]
        else:
            candidates += [
                self._root / "ai" / ".venv" / "bin" / "python",
                self._root / ".venv" / "bin" / "python",
                self._root / "backend" / ".venv" / "bin" / "python",
            ]
        candidates.append(Path(sys.executable))
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return sys.executable

    def start(self, camera_id: UUID | str, camera_number: int, stream_url: Optional[str]) -> dict:
        key = str(camera_id)
        with self._lock:
            existing = self._processes.get(key)
            if existing is not None and existing.poll() is None:
                return self.status(camera_id, camera_number)
            self._processes.pop(key, None)

            settings = get_settings()
            port = self._preview_port(camera_number)
            python_exe = self._python_executable()
            cmd = [
                python_exe, "-m", "ai.main",
                "--camera-id", key,
                "--source", self._source(stream_url),
                "--preview-port", str(port),
            ]
            env = os.environ.copy()
            env.update({
                "BACKEND_URL": settings.backend_url,
                "SERVICE_KEY": settings.ai_service_key,
                "PREVIEW_HOST": "0.0.0.0",
                "PREVIEW_PORT": str(port),
            })
            # Make ``ai`` importable even when uvicorn was started from backend/.
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(self._root), env.get("PYTHONPATH", "")]))

            log_path = self._log_dir / f"CAM-{int(camera_number):03d}.log"
            try:
                log_file = open(log_path, "a", encoding="utf-8", buffering=1)
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self._root),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                    preexec_fn=_die_with_parent if os.name != "nt" else None,
                )
                process._border_sentinel_log = log_file
            except OSError as exc:
                self._last_errors[key] = str(exc)
                try:
                    log_file.close()
                except Exception:
                    pass
                log.exception("Could not start AI worker for %s", key)
                return {"running": False, "status": "start_failed", "error": str(exc), "preview_port": port}

            self._processes[key] = process
            self._last_errors.pop(key, None)
            log.info("Started AI worker for %s (PID=%s, python=%s, source=%s, preview=%s)", key, process.pid, python_exe, self._source(stream_url), port)
            # Give Python a moment to import the model and bind the preview
            # port. This turns immediate startup failures into useful API
            # responses instead of a misleading permanent "LIVE" state.
            # Give the worker a short startup window, but do not declare a
            # healthy camera just because the Python process is alive. The
            # frontend polls /worker and the preview endpoint while the AI
            # model and camera source finish opening.
            time.sleep(0.5)
            if process.poll() is not None:
                self._processes.pop(key, None)
                message = f"AI worker exited during startup (code {process.returncode}). See {log_path}"
                self._last_errors[key] = message
                return {"running": False, "status": "start_failed", "exit_code": process.returncode, "error": message, "log_file": str(log_path), "preview_port": port}
            return {"running": True, "status": "starting", "pid": process.pid, "preview_port": port, "log_file": str(log_path)}

    def stop(self, camera_id: UUID | str) -> bool:
        key = str(camera_id)
        with self._lock:
            process = self._processes.pop(key, None)
        if process is None:
            return False
        if process.poll() is None:
            try:
                if os.name == "nt":
                    # CTRL_BREAK is graceful when the child owns a console,
                    # but GUI/service-launched processes may not have one.
                    # Fall back to terminate so a webcam handle cannot be
                    # left behind after logout.
                    try:
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                        process.wait(timeout=3)
                    except (OSError, subprocess.TimeoutExpired):
                        process.terminate()
                        process.wait(timeout=3)
                else:
                    process.terminate()
                    process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        log_file = getattr(process, "_border_sentinel_log", None)
        if log_file:
            try: log_file.close()
            except Exception: pass
        log.info("Stopped AI worker for %s", key)
        return True

    def restart(self, camera_id: UUID | str, camera_number: int, stream_url: Optional[str]) -> dict:
        self.stop(camera_id)
        return self.start(camera_id, camera_number, stream_url)

    def status(self, camera_id: UUID | str, camera_number: int) -> dict:
        key = str(camera_id)
        with self._lock:
            process = self._processes.get(key)
            if process is None:
                return {"running": False, "status": "stopped", "ai_error": self._last_errors.get(key), "preview_port": self._preview_port(camera_number)}
            code = process.poll()
            if code is None:
                return {"running": True, "status": "running", "pid": process.pid, "preview_port": self._preview_port(camera_number)}
            self._processes.pop(key, None)
            return {"running": False, "status": "exited", "ai_error": self._last_errors.get(key) or f"AI worker exited with code {code}", "preview_port": self._preview_port(camera_number)}

    def stop_all(self) -> None:
        for key in list(self._processes):
            self.stop(key)


worker_manager = CameraWorkerManager()
