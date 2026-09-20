"""Manage the single AI video-report service the backend starts on its own.

This is what backs the dashboard's "Analyze" page. It is one long-running
process for the whole backend lifetime (not one per camera): upload a clip,
it gets analyzed in the background, and the report is POSTed back to the
backend as alerts. See ai/upload_main.py for the service itself.
"""
from __future__ import annotations

import ctypes
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from threading import RLock
from typing import Optional

from app.core.config import get_settings

log = logging.getLogger(__name__)

_PR_SET_PDEATHSIG = 1


def _die_with_parent():
    """Same reasoning as camera_worker.py's _die_with_parent: without this,
    a `python -m ai.upload_main` child can survive a backend restart
    (`--reload`, crash, etc.) as an orphan holding port 8002, so the new
    backend process can never start its own copy — the exact kind of
    silent port conflict that made Analyze look broken before. Linux-only;
    harmless no-op elsewhere."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(_PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        pass


class AnalysisServiceManager:
    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._lock = RLock()
        self._root = Path(__file__).resolve().parents[3]
        self._log_dir = self._root / "runtime" / "ai-logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _python_executable(self) -> str:
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

    def start(self) -> dict:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return {"running": True, "pid": self._process.pid}

            settings = get_settings()
            cmd = [
                self._python_executable(), "-m", "ai.upload_main",
                "--upload-api-port", str(settings.ai_upload_api_port),
            ]
            env = os.environ.copy()
            env.update({
                "BACKEND_URL": settings.backend_url,
                "SERVICE_KEY": settings.ai_service_key,
            })
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(self._root), env.get("PYTHONPATH", "")]))

            log_path = self._log_dir / "video-analysis.log"
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
                log.exception("Could not start video-analysis service")
                return {"running": False, "error": str(exc)}

            self._process = process
            log.info(
                "Started video-analysis service (PID=%s) on :%s — see %s",
                process.pid, settings.ai_upload_api_port, log_path,
            )
            return {"running": True, "pid": process.pid, "api_port": settings.ai_upload_api_port}

    def stop(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
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
        log.info("Stopped video-analysis service")

    def status(self) -> dict:
        with self._lock:
            if self._process is None:
                return {"running": False}
            code = self._process.poll()
            if code is None:
                return {"running": True, "pid": self._process.pid}
            return {"running": False, "exit_code": code}


analysis_service_manager = AnalysisServiceManager()
