"""Emit a targeted public npm lock and its hash/provenance from read-only CI."""

import hashlib
import json
import os
from pathlib import Path

lock_path = "apps/web/package-lock.json"
metadata_path = "requirements/resolution.json"
metadata = json.loads(Path(metadata_path).read_text())
metadata["sha256"][lock_path] = hashlib.sha256(Path(lock_path).read_bytes()).hexdigest()
metadata.setdefault("updates", []).append({
    "source_commit": os.environ["GITHUB_SHA"],
    "artifact": lock_path,
    "reason": "PostCSS 8.5.23 advisory remediation",
})
Path(metadata_path).write_text(json.dumps(metadata, indent=2) + "\n")
for path in (lock_path, metadata_path):
    content = Path(path).read_text()
    chunks = [content[index:index + 12000] for index in range(0, len(content), 12000)]
    for index, chunk in enumerate(chunks):
        print("WEB_LOCK_CHUNK=" + json.dumps({
            "path": path, "part": index, "total": len(chunks), "content": chunk,
        }), flush=True)
