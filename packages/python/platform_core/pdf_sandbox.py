"""No-network PDF container: scan bounded requests on a private shared volume."""

import logging
import os
import shutil
import time
from pathlib import Path

from platform_core.pdf_isolation import MAX_INPUT_BYTES, PDFProcessorUnavailable, merge_pdfs_isolated
from platform_core.pdf_merge import InvalidPDF

logger = logging.getLogger(__name__)
ROOT = Path(os.environ.get("PDF_SANDBOX_ROOT", "/sandbox-jobs"))


def process_one(directory: Path) -> bool:
    if directory.is_symlink() or not directory.is_dir():
        return False
    ready, processing, done = (directory / name for name in ("request.ready", "processing", "done"))
    if done.exists():
        return False
    if ready.exists():
        ready.rename(processing)
    if not processing.is_file() or processing.is_symlink():
        return False
    try:
        count = int(processing.read_text())
        if not 2 <= count <= 10:
            raise InvalidPDF("invalid PDF count")
        paths = [directory / f"{index}.pdf" for index in range(count)]
        if any(not path.is_file() or path.is_symlink() for path in paths):
            raise InvalidPDF("missing PDF input")
        if sum(path.stat().st_size for path in paths) > MAX_INPUT_BYTES:
            raise InvalidPDF("PDF inputs exceed size limit")
        output = merge_pdfs_isolated([path.read_bytes() for path in paths])
        (directory / "result.pdf").write_bytes(output)
        status = "ok"
    except InvalidPDF:
        status = "invalid"
    except (PDFProcessorUnavailable, OSError, ValueError):
        logger.exception("pdf_sandbox_processing_failed")
        status = "error"
    # Renaming the status file makes completion visible to the worker atomically.
    (directory / "done.tmp").write_text(status)
    (directory / "done.tmp").replace(done)
    return True


def serve() -> None:
    logging.basicConfig(level=logging.INFO)
    ROOT.mkdir(parents=True, exist_ok=True)
    while True:
        for directory in ROOT.iterdir():
            if not directory.name.startswith("job-") or directory.is_symlink():
                continue
            try:
                if time.time() - directory.stat().st_mtime > 30 * 60:
                    shutil.rmtree(directory)
                else:
                    process_one(directory)
            except (OSError, ValueError):
                logger.exception("pdf_sandbox_request_failed")
        Path("/tmp/pdf-sandbox-heartbeat").touch()
        time.sleep(0.2)


if __name__ == "__main__":
    serve()
