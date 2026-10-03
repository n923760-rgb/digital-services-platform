"""Bounded, local text-to-DOCX formatting; no intake, storage or paid integration."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

TEMPLATE_ID = "formal-ar-v1"
MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_TITLE_CHARS = 200
MAX_BLOCKS = 200
MAX_BLOCK_CHARS = 10_000
MAX_TEXT_CHARS = 40_000
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class InvalidOfficeInput(ValueError):
    """Expected rejection with a sanitized code; never includes submitted text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OfficeOutputLimitExceeded(RuntimeError):
    """Formatting failed; a future delivery adapter must not send partial bytes."""


@dataclass(frozen=True)
class OfficeBlock:
    text: str
    kind: str = "paragraph"
    direction: str = "auto"


@dataclass(frozen=True)
class OfficeDocument:
    title: str
    blocks: tuple[OfficeBlock, ...]
    template_id: str = TEMPLATE_ID


@dataclass(frozen=True)
class DocxArtifact:
    content: bytes
    sha256: str
    template_id: str
    mime_type: str = MIME_TYPE


def _validate_text(text: object, limit: int) -> None:
    if not isinstance(text, str):
        raise InvalidOfficeInput("invalid_text_type")
    if len(text) > limit:
        raise InvalidOfficeInput("text_limit")
    # XML 1.0 permits tabs and line endings, but not C0 controls or surrogates.
    if any(not (c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF
                or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
           for c in text):
        raise InvalidOfficeInput("invalid_xml_character")


def _validate(document: OfficeDocument) -> None:
    if not isinstance(document, OfficeDocument):
        raise InvalidOfficeInput("invalid_document_type")
    if document.template_id != TEMPLATE_ID:
        raise InvalidOfficeInput("unsupported_template")
    _validate_text(document.title, MAX_TITLE_CHARS)
    if not document.title.strip() or any(c in document.title for c in "\t\r\n"):
        raise InvalidOfficeInput("invalid_title")
    if not isinstance(document.blocks, tuple) or not 1 <= len(document.blocks) <= MAX_BLOCKS:
        raise InvalidOfficeInput("invalid_blocks")
    total = len(document.title)
    meaningful = False
    for block in document.blocks:
        if not isinstance(block, OfficeBlock):
            raise InvalidOfficeInput("invalid_block_type")
        if block.kind not in ("paragraph", "heading"):
            raise InvalidOfficeInput("unsupported_block_kind")
        if block.direction not in ("auto", "rtl", "ltr"):
            raise InvalidOfficeInput("unsupported_direction")
        _validate_text(block.text, MAX_TITLE_CHARS if block.kind == "heading" else MAX_BLOCK_CHARS)
        if block.kind == "heading" and (
            not block.text.strip() or any(c in block.text for c in "\t\r\n")
        ):
            raise InvalidOfficeInput("invalid_heading")
        total += len(block.text)
        if total > MAX_TEXT_CHARS:
            raise InvalidOfficeInput("document_text_limit")
        meaningful = meaningful or bool(block.text.strip())
    if not meaningful:
        raise InvalidOfficeInput("empty_body")


def _w(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    return ET.SubElement(parent, f"w:{tag}", {f"w:{key}": val for key, val in attrs.items()})


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _direction(text: str) -> str:
    for char in text:
        bidi = unicodedata.bidirectional(char)
        if bidi in ("R", "AL"):
            return "rtl"
        if bidi == "L":
            return "ltr"
    return "rtl"


def _segments(text: str, default: str):
    """Keep identifiers and their opening punctuation out of RTL text runs."""
    following = []
    next_direction = default
    for char in reversed(text):
        bidi = unicodedata.bidirectional(char)
        if bidi in ("R", "AL", "AN"):
            next_direction = "rtl"
        elif bidi in ("L", "EN"):
            next_direction = "ltr"
        following.append(next_direction)
    following.reverse()
    start = 0
    current = default
    for index, char in enumerate(text):
        bidi = unicodedata.bidirectional(char)
        direction = "rtl" if bidi in ("R", "AL", "AN") else (
            "ltr" if bidi in ("L", "EN") else current
        )
        if char in "<([{" or (char in "\"'" and (
            index == 0 or text[index - 1].isspace() or text[index - 1] in "<([{"
        )):
            direction = following[index]
        if direction != current:
            if index > start:
                yield text[start:index], current
            start, current = index, direction
    if start < len(text):
        yield text[start:], current


def _paragraph(body: ET.Element, text: str, style: str, direction: str = "auto") -> None:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    direction = _direction(text) if direction == "auto" else direction
    p = _w(body, "p")
    props = _w(p, "pPr")
    _w(props, "pStyle", val=style)
    _w(props, "bidi", val="1" if direction == "rtl" else "0")
    # Logical alignment follows paragraph direction in modern Word and LibreOffice.
    _w(props, "jc", val="start")
    for segment, run_direction in _segments(text, direction):
        # Preserve explicit embedding for opposite-direction text.
        container = p
        if run_direction != direction:
            container = _w(p, "dir", val=run_direction)
        run = _w(container, "r")
        _w(_w(run, "rPr"), "rtl", val="1" if run_direction == "rtl" else "0")
        for token in re.split(r"([\t\n])", segment):
            if token in ("\t", "\n"):
                _w(run, "tab" if token == "\t" else "br")
            elif token:
                element = _w(run, "t")
                element.set("xml:space", "preserve")
                element.text = token


def _styles() -> bytes:
    root = ET.Element("w:styles", {"xmlns:w": W_NS})
    for name, size in (("Normal", "24"), ("Title", "36"), ("Heading1", "28")):
        attrs = {"type": "paragraph", "styleId": name}
        if name == "Normal":
            attrs["default"] = "1"
        style = _w(root, "style", **attrs)
        _w(style, "name", val={"Heading1": "heading 1"}.get(name, name))
        if name != "Normal":
            _w(style, "basedOn", val="Normal")
        _w(style, "next", val="Normal")
        _w(style, "qFormat")
        p = _w(style, "pPr")
        if name != "Normal":
            _w(p, "keepNext")
        _w(p, "widowControl")
        _w(p, "spacing", before="240" if name == "Heading1" else "0",
           after="240" if name == "Title" else "160", line="300", lineRule="auto")
        if name == "Heading1":
            _w(p, "outlineLvl", val="0")
        r = _w(style, "rPr")
        _w(r, "rFonts", ascii="Arial", hAnsi="Arial", cs="Arial", eastAsia="Arial")
        if name != "Normal":
            _w(r, "b")
            _w(r, "bCs")
        _w(r, "color", val="000000")
        _w(r, "sz", val=size)
        _w(r, "szCs", val=size)
        _w(r, "lang", val="en-US", bidi="ar-SA")
    return _xml(root)


def _relationships(entries: tuple[tuple[str, str], ...]) -> bytes:
    root = ET.Element("Relationships", {"xmlns": REL_NS})
    for index, (kind, target) in enumerate(entries, 1):
        ET.SubElement(root, "Relationship", {
            "Id": f"rId{index}", "Type": f"{OFFICE_REL_NS}/{kind}", "Target": target,
        })
    return _xml(root)


def render_docx(document: OfficeDocument) -> DocxArtifact:
    """Return editable DOCX bytes; caller owns storage, expiry, errors and delivery."""
    _validate(document)
    root = ET.Element("w:document", {"xmlns:w": W_NS})
    body = _w(root, "body")
    _paragraph(body, document.title, "Title")
    for block in document.blocks:
        _paragraph(body, block.text, "Heading1" if block.kind == "heading" else "Normal",
                   block.direction)
    section = _w(body, "sectPr")
    _w(section, "pgSz", w="12240", h="15840")
    _w(section, "pgMar", top="1440", right="1440", bottom="1440", left="1440",
       header="720", footer="720", gutter="0")
    types = ET.Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
    ET.SubElement(types, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(types, "Default", {"Extension": "xml", "ContentType": "application/xml"})
    for path, kind in (("document", "document.main"), ("styles", "styles")):
        ET.SubElement(types, "Override", {
            "PartName": f"/word/{path}.xml",
            "ContentType": f"application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml",
        })
    parts = {
        "[Content_Types].xml": _xml(types),
        "_rels/.rels": _relationships((("officeDocument", "word/document.xml"),)),
        "word/document.xml": _xml(root),
        "word/styles.xml": _styles(),
        "word/_rels/document.xml.rels": _relationships((("styles", "styles.xml"),)),
    }
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path, content in parts.items():
            info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0x20
            archive.writestr(info, content, compresslevel=6)
    data = output.getvalue()
    if len(data) > MAX_OUTPUT_BYTES:
        raise OfficeOutputLimitExceeded("office_output_limit")
    return DocxArtifact(data, sha256(data).hexdigest(), document.template_id)
