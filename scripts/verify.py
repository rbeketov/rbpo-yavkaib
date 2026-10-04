#!/usr/bin/env python3
"""Run offline MVP checks and optionally save results tied to code hashes."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def source_hashes():
    files = [ROOT / "manage.py", ROOT / "requirements.txt"]
    for directory in ("taskflow", "tracker", "templates", "static", "scripts"):
        files.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".html", ".css"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    env = dict(os.environ, TASKFLOW_SECRET_KEY=secrets.token_urlsafe(64), TASKFLOW_DEBUG="1")
    checks = [
        ("dependency-consistency", ["-m", "pip", "check"], {}),
        ("django-system-check", ["manage.py", "check"], {}),
        ("migration-consistency", ["manage.py", "makemigrations", "--check", "--dry-run"], {}),
        ("behavior-and-security-tests", ["manage.py", "test", "--verbosity", "2"], {}),
        ("non-debug-configuration-check", ["manage.py", "check", "--deploy", "--fail-level", "WARNING"],
         {"TASKFLOW_DEBUG": "0"}),
    ]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit.stdout.strip() if commit.returncode == 0 else "archive-without-git",
        "python": sys.version.split()[0],
        "dependencies": {name: importlib.metadata.version(name) for name in ("Django", "asgiref", "sqlparse")},
        "scope": "Local automated MVP checks; not a vulnerability audit or independent human review.",
        "source_sha256": source_hashes(), "checks": [],
    }
    for name, command, extra_env in checks:
        result = subprocess.run([sys.executable, *command], cwd=ROOT, env={**env, **extra_env},
                                capture_output=True, text=True)
        output = (result.stdout + result.stderr).replace(str(ROOT), "<checkout>")
        report["checks"].append({"name": name, "command": ["python", *command],
                                  "returncode": result.returncode, "output": output})
        print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {name}")
        if result.returncode:
            print(output)
    report["passed"] = all(check["returncode"] == 0 for check in report["checks"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"Report: {args.output}")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
