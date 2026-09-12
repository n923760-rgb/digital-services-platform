"""Compose-only health probe: cross-container PDF processing, no external service."""

from io import BytesIO

from pypdf import PdfReader, PdfWriter

from platform_core.config import get_settings
from platform_core.pdf_sandbox_client import merge_pdfs_in_sandbox


def main() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    data = BytesIO()
    writer.write(data)
    writer.close()
    result = merge_pdfs_in_sandbox([data.getvalue(), data.getvalue()],
                                   get_settings().pdf_sandbox_root)
    if len(PdfReader(BytesIO(result)).pages) != 2:
        raise RuntimeError("PDF sandbox failed to merge two test pages")
    print("pdf sandbox: ok")


if __name__ == "__main__":
    main()
