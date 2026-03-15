#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick backend starter for Director Mode (no frontend needed).
- Creates venv under backend/.venv if missing
- Installs requirements
- Checks DASHSCOPE_API_KEY
- Starts FastAPI with uvicorn
- Optional: submit a demo job from JSON and poll result

Usage examples:
  python backend/start_backend.py --port 8080 --reload
  python backend/start_backend.py --run-demo --paper-json backend/demo_paper.json
"""
import argparse
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]  # repo root
BACKEND = ROOT / "backend"
VENV = BACKEND / ".venv"
IS_WIN = os.name == "nt"


def venv_python() -> str:
    if IS_WIN:
        return str(VENV / "Scripts" / "python.exe")
    return str(VENV / "bin" / "python")


def venv_pip() -> str:
    if IS_WIN:
        return str(VENV / "Scripts" / "pip.exe")
    return str(VENV / "bin" / "pip")


def ensure_venv():
    if not VENV.exists():
        print("[setup] creating venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    print(f"[setup] venv at {VENV}")


def install_requirements():
    req = BACKEND / "requirements.txt"
    print("[setup] upgrading pip ...")
    subprocess.run([venv_pip(), "install", "-U", "pip"], check=True)
    print("[setup] installing requirements ...")
    subprocess.run([venv_pip(), "install", "-r", str(req)], check=True)


def check_env_or_exit():
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("[ERROR] Please set DASHSCOPE_API_KEY in your environment (not committed).", file=sys.stderr)
        print("        Example (cmd):   set DASHSCOPE_API_KEY=sk-xxx", file=sys.stderr)
        print("        Example (PowerShell):  $env:DASHSCOPE_API_KEY=\"sk-xxx\"", file=sys.stderr)
        sys.exit(1)


def start_uvicorn(host: str, port: int, reload: bool) -> subprocess.Popen:
    cmd = [venv_python(), "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    if reload:
        cmd.append("--reload")
    print("[run] ", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=str(BACKEND))


def wait_http_ready(url: str, timeout_sec: int = 60) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=3) as resp:
                if resp.status in (200, 404):
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_demo(port: int, json_path: Path = None, poll: bool = True):
    if json_path and json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        payload = {
            "paper_title": "Demo Paper",
            "abstract": "This paper proposes a simple pipeline for generating a homepage hero GIF from textual concepts.",
            "concept_name": "Core Idea",
            "key_claims": ["Concise director prompts", "GIF under 12MB", "720p/24fps"],
            "scene_goals": ["Clarity", "Engagement"],
            "duration_sec": 6,
            "style": "educational",
            "fps": 24,
            "width": 720
        }
    job = post_json(f"http://127.0.0.1:{port}/api/director/generate-from-paper", payload)
    job_id = job.get("id")
    print(f"[demo] job id = {job_id}")
    if not poll or not job_id:
        return
    # poll status
    while True:
        time.sleep(3)
        info = get_json(f"http://127.0.0.1:{port}/api/director/jobs/{job_id}")
        print(f"[demo] status={info.get('status')} msg={info.get('message')} mp4={info.get('mp4_path')} gif={info.get('gif_path')}")
        if info.get("status") in ("SUCCEEDED", "FAILED", "NOT_FOUND"):
            break


def main():
    parser = argparse.ArgumentParser(description="Quick backend starter (Director Mode)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--run-demo", action="store_true", help="submit a demo job after server starts")
    parser.add_argument("--paper-json", type=str, help="path to a JSON file with paper fields (see backend/demo_paper.json)")
    args = parser.parse_args()

    ensure_venv()
    install_requirements()
    check_env_or_exit()

    # ensure outputs dir exists (read by app)
    out_dir = BACKEND / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # start server
    proc = start_uvicorn(args.host, args.port, args.reload)

    # wait for readiness
    ready = wait_http_ready(f"http://127.0.0.1:{args.port}/openapi.json", timeout_sec=90)
    if not ready:
        print("[error] server did not become ready in time", file=sys.stderr)
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(1)

    if args.run_demo:
        jp = Path(args.paper_json) if args.paper_json else None
        run_demo(args.port, jp)
        print("[demo] done; leaving server running. Press Ctrl+C to stop.")

    # keep foreground if not exited
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("[stop] terminating server...")
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
