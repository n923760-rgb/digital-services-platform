"""Bounded file-based IPC to a fresh PDF parser process, never in the ARQ worker."""

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from platform_core.pdf_merge import InvalidPDF

MAX_INPUT_BYTES = 40 * 1024 * 1024
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
PDF_TIMEOUT_SECONDS = 75


class PDFProcessorUnavailable(RuntimeError):
    pass


def merge_pdfs_isolated(documents: list[bytes]) -> bytes:
    if not 2 <= len(documents) <= 10 or sum(map(len, documents)) > MAX_INPUT_BYTES:
        raise InvalidPDF("invalid number or total size of PDFs")
    with tempfile.TemporaryDirectory(prefix="pdf-job-") as directory:
        base = Path(directory)
        paths = []
        for index, document in enumerate(documents):
            path = base / f"{index}.pdf"
            path.write_bytes(document)
            paths.append(str(path))
        output = base / "merged.pdf"
        # The child receives no provider credentials or inherited connection handles.
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).with_name("pdf_runner.py")), str(output), *paths],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=True, cwd=directory,
                env={"PATH": os.defpath, "HOME": directory, "LC_ALL": "C.UTF-8"},
            )
        except OSError as exc:
            raise PDFProcessorUnavailable("PDF processor could not start") from exc
        try:
            status = process.wait(timeout=PDF_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise PDFProcessorUnavailable("PDF processing timed out") from exc
        if status == 2:
            raise InvalidPDF("PDF failed validation or output size limit")
        if status != 0:
            raise PDFProcessorUnavailable("PDF processing failed")
        if not output.is_file() or not 0 < output.stat().st_size <= MAX_OUTPUT_BYTES:
            raise PDFProcessorUnavailable("PDF output missing or oversized")
        return output.read_bytes()
