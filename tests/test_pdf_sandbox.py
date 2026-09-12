"""Exercise the private-volume protocol and failure without Docker or customer access."""

import asyncio
from io import BytesIO

import pytest
from platform_core.pdf_isolation import PDFProcessorUnavailable
from platform_core.pdf_merge import InvalidPDF
from platform_core.pdf_sandbox import process_one
from platform_core.pdf_sandbox_client import merge_pdfs_in_sandbox
from pypdf import PdfReader, PdfWriter


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    data = BytesIO()
    writer.write(data)
    writer.close()
    return data.getvalue()


async def serve_once(root):
    for _ in range(40):
        jobs = list(root.glob("job-*"))
        if jobs and (jobs[0] / "request.ready").is_file():
            await asyncio.to_thread(process_one, jobs[0])
            return
        await asyncio.sleep(0.025)
    raise AssertionError("sandbox did not receive the request")


@pytest.mark.asyncio
async def test_sandbox_delivers_checked_pdf_and_removes_inputs(tmp_path):
    documents = [blank_pdf(), blank_pdf()]
    request = asyncio.create_task(asyncio.to_thread(merge_pdfs_in_sandbox, documents, str(tmp_path)))
    await serve_once(tmp_path)
    result = await request
    assert len(PdfReader(BytesIO(result)).pages) == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_invalid_input_fails_without_leaving_shared_files(tmp_path):
    request = asyncio.create_task(asyncio.to_thread(
        merge_pdfs_in_sandbox, [blank_pdf(), b"%PDF-broken"], str(tmp_path),
    ))
    await serve_once(tmp_path)
    with pytest.raises(InvalidPDF):
        await request
    assert list(tmp_path.iterdir()) == []


def test_unavailable_sandbox_times_out_and_cleans_up(tmp_path):
    with pytest.raises(PDFProcessorUnavailable, match="timed out"):
        merge_pdfs_in_sandbox([blank_pdf(), blank_pdf()], str(tmp_path), timeout=0.2)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(PDFProcessorUnavailable, match="not configured"):
        merge_pdfs_in_sandbox([blank_pdf(), blank_pdf()], "")
