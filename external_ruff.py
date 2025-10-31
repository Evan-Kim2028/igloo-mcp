import json
import subprocess


def ruff_check(paths):
    result = subprocess.run(
        ["ruff", "check", *paths, "--output-format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout or "[]")
