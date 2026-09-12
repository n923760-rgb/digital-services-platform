"""Send PDF bytes to the no-network container through a private, bounded volume."""

import shutil
import tempfile
import time
from pathlib import Path

from platform_core.pdf_isolation import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, PDFProcessorUnavailable
from platform_core.pdf_merge import InvalidPDF


def merge_pdfs_in_sandbox(
    documents: list[bytes], root: str, *, timeout: float = 95,
) -> bytes:
    if not root:
        raise PDFProcessorUnavailable("PDF sandbox is not configured")
    if not 2 <= len(documents) <= 10 or sum(map(len, documents)) > MAX_INPUT_BYTES:
        raise InvalidPDF("invalid number or total size of PDFs")
    if not Path(root).is_dir():
        raise PDFProcessorUnavailable("PDF sandbox volume unavailable")
    directory = Path(tempfile.mkdtemp(prefix="job-", dir=root))
    try:
        for index, document in enumerate(documents):
            (directory / f"{index}.pdf").write_bytes(document)
        (directory / "request.ready").write_text(str(len(documents)))
        deadline = time.monotonic() + timeout
        done = directory / "done"
        while time.monotonic() < deadline:
            if done.is_file():
                status = done.read_text()
                if status == "invalid":
                    raise InvalidPDF("PDF failed validation")
                if status != "ok":
                    raise PDFProcessorUnavailable("PDF sandbox failed")
                output = directory / "result.pdf"
                if not output.is_file() or not 0 < output.stat().st_size <= MAX_OUTPUT_BYTES:
                    raise PDFProcessorUnavailable("PDF sandbox output invalid")
                result = output.read_bytes()
                if not result.startswith(b"%PDF-") or len(result) > MAX_OUTPUT_BYTES:
                    raise PDFProcessorUnavailable("PDF sandbox output invalid")
                return result
            time.sleep(0.1)
        raise PDFProcessorUnavailable("PDF sandbox timed out")
    except OSError as exc:
        raise PDFProcessorUnavailable("PDF sandbox volume failed") from exc
    finally:
        shutil.rmtree(directory, ignore_errors=True)
