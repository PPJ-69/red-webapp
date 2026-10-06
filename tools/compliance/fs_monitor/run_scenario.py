from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from .monitor import FileSystemMonitor, Violation, default_monitor_roots
except ImportError:
    from monitor import FileSystemMonitor, Violation, default_monitor_roots

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_scenario(command: list[str], roots: list[Path]) -> tuple[int, tuple[Violation, ...]]:
    monitor = FileSystemMonitor(roots)
    monitor.start()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=False)
    finally:
        violations = monitor.stop()
    report = {
        "status": "violations" if violations else "passed",
        "scenario": command,
        "writes": [violation.as_dict() for violation in violations],
    }
    print(json.dumps(report, indent=2))
    return result.returncode, violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor runtime filesystem paths for forbidden persistent data."
    )
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="Directory to monitor (repeatable; defaults to project and system temp roots).",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide a scenario command after --")

    roots = arguments.root or list(default_monitor_roots(PROJECT_ROOT))
    command_status, violations = run_scenario(command, roots)
    if command_status != 0:
        return command_status
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
