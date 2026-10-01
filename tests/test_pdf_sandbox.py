"""Exercise the private-volume protocol and failure without Docker or customer access."""

import asyncio
from io import BytesIO
from threading import Event, get_ident

import pytest
from platform_core import pdf_sandbox
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


def test_heartbeat_runs_while_bounded_job_blocks_the_scanner(monkeypatch):
    clock = [0.0]
    renewed = Event()
    touches = []
    removed = []
    monkeypatch.setattr(pdf_sandbox.time, "monotonic", lambda: clock[0])

    class HeartbeatFile:
        def touch(self):
            touches.append((clock[0], get_ident()))
            if clock[0] == 20:
                renewed.set()

        def unlink(self):
            removed.append(True)

    heartbeat = pdf_sandbox.ProgressHeartbeat(HeartbeatFile(), interval=0.01)
    with heartbeat:
        heartbeat.allow(85)
        # The scanner is blocked beyond the old ten-second health freshness window.
        clock[0] = 20
        assert renewed.wait(timeout=1)
        assert touches[-1][1] != get_ident()
    assert not heartbeat.thread.is_alive() and removed == [True]


def test_heartbeat_stops_after_job_deadline_and_idle_stall(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(pdf_sandbox.time, "monotonic", lambda: clock[0])
    path = tmp_path / "heartbeat"
    heartbeat = pdf_sandbox.ProgressHeartbeat(path)
    heartbeat.allow(85)
    clock[0] = 75
    assert heartbeat.pulse() and path.is_file()
    previous = path.stat().st_mtime_ns
    clock[0] = 85
    assert not heartbeat.pulse() and path.stat().st_mtime_ns == previous
    # Completing the job grants only the short idle progress window.
    heartbeat.allow(10)
    clock[0] = 94
    assert heartbeat.pulse()
    clock[0] = 95
    assert not heartbeat.pulse()
