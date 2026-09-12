"""Restricted subprocess entrypoint for deterministic PDF processing on Linux."""

import os
import resource
import sys
from pathlib import Path


def main() -> int:
    # Enforce limits before importing the PDF parser or opening customer data.
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_FSIZE, (24 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    # -I excludes both CWD and user site-packages; only trust this installed code directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from platform_core.pdf_merge import InvalidPDF, merge_pdfs

    if len(sys.argv) < 4:
        return 3
    try:
        documents = [Path(path).read_bytes() for path in sys.argv[2:]]
        output = merge_pdfs(documents)
        if len(output) > 20 * 1024 * 1024:
            return 2
        with open(sys.argv[1], "xb") as file:
            file.write(output)
        return 0
    except InvalidPDF:
        return 2
    except (OSError, MemoryError, ValueError):
        return 3


if __name__ == "__main__":
    os._exit(main())
