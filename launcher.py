"""
NodeRAG Launcher — double-click NodeRAG.exe to start everything.

Opens two console windows (API server + frontend dev server) then
opens the browser once the API is ready.
"""
import subprocess
import sys
import time
import webbrowser
import urllib.request
from pathlib import Path

# When frozen by PyInstaller sys.executable is the .exe path.
# When run as a plain script, __file__ is this file.
ROOT = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).parent
)


def _print(msg=""):
    print(msg, flush=True)


def wait_for_api(url="http://localhost:8000/api/", timeout=120):
    """Poll until the API responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main():
    _print("=" * 52)
    _print("  NodeRAG")
    _print("=" * 52)
    _print(f"  Project: {ROOT}")
    _print()

    # ── 1. API server ─────────────────────────────────────────────────────────
    _print("[1/3]  Starting API server on :8000 ...")
    subprocess.Popen(
        'start "NodeRAG — API :8000" cmd /k '
        'python -m uvicorn api.main:app --port 8000',
        cwd=str(ROOT),
        shell=True,
    )

    # ── 2. Frontend dev server ────────────────────────────────────────────────
    _print("[2/3]  Starting frontend on :5173 ...")
    subprocess.Popen(
        'start "NodeRAG — Frontend :5173" cmd /k '
        'npm run dev',
        cwd=str(ROOT / "frontend"),
        shell=True,
    )

    # ── 3. Wait for API, then open browser ───────────────────────────────────
    _print("[3/3]  Waiting for API (this takes ~15 s on first run) ...")
    ready = wait_for_api()
    if ready:
        _print("       API ready.")
    else:
        _print("       Timed out — opening browser anyway.")

    time.sleep(2)
    webbrowser.open("http://localhost:5173")

    _print()
    _print("  NodeRAG is running at  http://localhost:5173")
    _print()
    _print("  To stop: close the two server windows.")
    _print("  Press Enter to close this launcher window.")
    _print()

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
