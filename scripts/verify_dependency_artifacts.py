"""Verify the committed resolution fingerprints and runtime/dev/parser consistency."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pins(path):
    content = (ROOT / path).read_text()
    return dict(re.findall(r"^([a-zA-Z0-9_.-]+)==([^\\\n ]+)", content, re.MULTILINE))


def main():
    metadata = json.loads((ROOT / "requirements/resolution.json").read_text())
    for path, expected in metadata["sha256"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"lock fingerprint changed: {path}; resolve and review dependencies")
    runtime = pins("requirements/runtime.txt")
    development = pins("requirements/dev.txt")
    if any(development.get(name) != version for name, version in runtime.items()):
        raise ValueError("development lock diverges from runtime")
    if pins("requirements/sandbox.txt") != {"pypdf": runtime["pypdf"]}:
        raise ValueError("sandbox parser diverges from worker")
    print("Dependency fingerprints and runtime/dev/sandbox versions verified")


if __name__ == "__main__":
    main()
