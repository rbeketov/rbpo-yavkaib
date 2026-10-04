#!/usr/bin/env python3
"""Set up a local environment without modifying any global Python installation."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent.parent


def main():
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12+ is required. Run this script with python3.12.")
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.create(environment, with_pip=True)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    path = ROOT / ".env"
    if not path.exists():
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write(f"TASKFLOW_SECRET_KEY={secrets.token_urlsafe(64)}\n"
                       "TASKFLOW_DEBUG=1\nTASKFLOW_ALLOWED_HOSTS=localhost,127.0.0.1\n")
    print("Ready. Load .env into your shell, then migrate and seed_demo (see README.md).")


if __name__ == "__main__":
    main()
