"""Developer task runner for igloo-mcp."""

from __future__ import annotations

import subprocess
import sys
from typing import Callable, Dict


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def format_code() -> None:
    _run(["uv", "run", "ruff", "format", "src/", "tests/"])


def lint() -> None:
    _run(["uv", "run", "ruff", "check", "src/", "tests/"])


def typecheck() -> None:
    _run(["uv", "run", "mypy", "src/"])


def test() -> None:
    _run(["uv", "run", "pytest", "-q"])


TASKS: Dict[str, Callable[[], None]] = {
    "format": format_code,
    "lint": lint,
    "typecheck": typecheck,
    "test": test,
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        available = ", ".join(sorted(TASKS))
        print(f"Usage: uv run tasks.py <{available}>")
        sys.exit(1)
    TASKS[sys.argv[1]]()


if __name__ == "__main__":
    main()
