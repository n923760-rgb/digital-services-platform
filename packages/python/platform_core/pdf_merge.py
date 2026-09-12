"""Bounded deterministic PDF merge and independent output verification."""

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject


class InvalidPDF(ValueError):
    pass


DISALLOWED_KEYS = {
    "/AA", "/AcroForm", "/AF", "/Annots", "/Collection", "/EmbeddedFiles", "/EF",
    "/Filespec", "/FS",
    "/JS", "/JavaScript", "/Launch", "/Names", "/OpenAction", "/RichMedia",
    "/SubmitForm", "/ImportData", "/XFA", "/URI", "/GoToR", "/Rendition",
    "/Movie", "/Sound", "/Screen", "/3D",
}
MAX_PDF_OBJECTS = 50_000
MAX_PDF_DEPTH = 64


def reject_active_content(reader: PdfReader) -> None:
    """Inspect the reachable object graph without decoding page/image streams."""
    pending = [(reader.trailer, 0)]
    seen = set()
    inspected = 0
    while pending:
        value, depth = pending.pop()
        inspected += 1
        if depth > MAX_PDF_DEPTH or inspected > MAX_PDF_OBJECTS * 2:
            raise InvalidPDF("PDF object graph exceeds safety limits")
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > MAX_PDF_OBJECTS:
                raise InvalidPDF("PDF object graph exceeds safety limits")
            pending.append((value.get_object(), depth + 1))
        elif isinstance(value, (DictionaryObject, ArrayObject)):
            key = id(value)
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > MAX_PDF_OBJECTS:
                raise InvalidPDF("PDF object graph exceeds safety limits")
            if isinstance(value, DictionaryObject):
                if DISALLOWED_KEYS.intersection(value.keys()):
                    raise InvalidPDF("PDF contains unsupported active content")
                children = value.values()
            else:
                children = value
            pending.extend((child, depth + 1) for child in children)


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
            reject_active_content(reader)
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
        reject_active_content(verified)
        return result
    except InvalidPDF:
        raise
    except (PdfReadError, OSError, RecursionError, TypeError, ValueError) as exc:
        raise InvalidPDF("unreadable PDF") from exc
    finally:
        writer.close()
