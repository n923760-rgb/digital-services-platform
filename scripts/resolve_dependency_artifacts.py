"""Resolve public images and emit bounded CI lock chunks; never uses provider secrets."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = [
    "python:3.12-slim", "node:22-alpine", "postgres:16-alpine",
    "redis:7-alpine", "caddy:2-alpine", "adobe/s3mock:5.2.2",
]


def run(*args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    runtime = (ROOT / "requirements/runtime.txt").read_text()
    pypdf = re.search(r"^pypdf==([^\\\n ]+)", runtime, re.MULTILINE).group(1)
    (ROOT / "requirements/sandbox.in").write_text(f"pypdf=={pypdf}\n")
    run(
        "pip-compile", "--quiet", "--generate-hashes", "--no-emit-index-url",
        "--no-emit-trusted-host", "--output-file", "requirements/sandbox.txt",
        "requirements/sandbox.in",
    )
    run(
        "npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit",
        "--no-fund", cwd=ROOT / "apps/web",
    )
    images = {}
    for image in IMAGES:
        print(f"Resolving immutable image: {image}", flush=True)
        run("docker", "pull", image)
        digest = json.loads(run("docker", "image", "inspect", image))[0]["RepoDigests"][0]
        images[image] = image + "@" + digest.split("@", 1)[1]
    paths = [
        "requirements/runtime.txt", "requirements/dev.txt", "requirements/build.txt",
        "requirements/sandbox.txt", "apps/web/package-lock.json",
    ]
    metadata = {
        "source_commit": os.environ["GITHUB_SHA"],
        "images": images,
        "python": run("python", "--version").split()[1],
        "node": run("node", "--version").lstrip("v"),
        "resolver": "pip-tools==7.5.0; pip==25.1.1",
        "sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
    }
    metadata_path = "requirements/resolution.json"
    (ROOT / metadata_path).write_text(json.dumps(metadata, indent=2) + "\n")
    for path in [*paths, metadata_path]:
        content = (ROOT / path).read_text()
        chunks = [content[i:i + 12000] for i in range(0, len(content), 12000)]
        for index, chunk in enumerate(chunks):
            print("DEPENDENCY_LOCK_CHUNK=" + json.dumps({
                "path": path, "part": index, "total": len(chunks), "content": chunk,
            }), flush=True)


if __name__ == "__main__":
    main()
