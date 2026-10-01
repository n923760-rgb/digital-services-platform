"""Emit public lock chunks from read-only CI without writing repository refs."""

import json
from pathlib import Path

content = Path("requirements/audit.txt").read_text()
chunks = [content[index:index + 12000] for index in range(0, len(content), 12000)]
for index, chunk in enumerate(chunks):
    print("AUDIT_LOCK_CHUNK=" + json.dumps({
        "part": index, "total": len(chunks), "content": chunk,
    }), flush=True)
