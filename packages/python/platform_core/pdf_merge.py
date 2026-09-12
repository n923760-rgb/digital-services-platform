"""Bounded deterministic PDF merge and independent output verification."""

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


class InvalidPDF(ValueError):
    pass


def merge_pdfs(documents: list[bytes]) -> bytes:
    if not 2 <= len(documents) <= 10 or sum(map(len, documents)) > 40 * 1024 * 1024:
        raise InvalidPDF("invalid number or total size of PDFs")
    writer = PdfWriter()
    total_pages = 0
    try:
        for document in documents:
            if not document.startswith(b"%PDF-"):
                raise InvalidPDF("not a PDF")
            reader = PdfReader(BytesIO(document), strict=True)
            if reader.is_encrypted:
                raise InvalidPDF("encrypted PDF")
            pages = len(reader.pages)
            if pages == 0 or total_pages + pages > 200:
                raise InvalidPDF("invalid total page count")
            total_pages += pages
            writer.append(reader, import_outline=False)
        output = BytesIO()
        writer.write(output)
        result = output.getvalue()
        verified = PdfReader(BytesIO(result), strict=True)
        if not result.startswith(b"%PDF-") or len(verified.pages) != total_pages:
            raise InvalidPDF("merged PDF failed quality check")
        return result
    except (PdfReadError, OSError, RecursionError) as exc:
        raise InvalidPDF("unreadable PDF") from exc
    finally:
        writer.close()
