"""Pure executor checks, collected by pytest and runnable without third-party deps."""

import unittest
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from platform_core.office_docx import (
    MAX_BLOCK_CHARS,
    MAX_BLOCKS,
    MAX_TEXT_CHARS,
    MAX_TITLE_CHARS,
    MIME_TYPE,
    REL_NS,
    TEMPLATE_ID,
    W_NS,
    InvalidOfficeInput,
    OfficeBlock,
    OfficeDocument,
    OfficeOutputLimitExceeded,
    render_docx,
)

NS = {"w": W_NS}
BASE = OfficeDocument("تقرير العمل", (OfficeBlock("هذا نص عربي قابل للتعديل."),))


def document_xml(artifact):
    with ZipFile(BytesIO(artifact.content)) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def paragraph_text(element):
    return "".join("\n" if node.tag == f"{{{W_NS}}}br" else
                   "\t" if node.tag == f"{{{W_NS}}}tab" else
                   (node.text or "").replace("\u202a", "").replace("\u202c", "")
                   for node in element.iter()
                   if node.tag in {f"{{{W_NS}}}{tag}" for tag in ("t", "br", "tab")})


class OfficeDocxTests(unittest.TestCase):
    def test_preserves_editable_text_order_spaces_breaks_and_tabs(self):
        blocks = (OfficeBlock("مقدمة", "heading"), OfficeBlock("  أ ب  \r\nج\tد\rهـ\n"),
                  OfficeBlock(""), OfficeBlock("Final paragraph", direction="ltr"))
        result = render_docx(replace(BASE, blocks=blocks))
        paragraphs = document_xml(result).findall("w:body/w:p", NS)
        self.assertEqual([paragraph_text(p) for p in paragraphs],
                         [BASE.title, "مقدمة", "  أ ب  \nج\tد\nهـ\n", "", "Final paragraph"])
        self.assertEqual(paragraphs[1].find("w:pPr/w:pStyle", NS).get(f"{{{W_NS}}}val"),
                         "Heading1")

    def test_escapes_markup_and_never_creates_hyperlinks_or_fields(self):
        text = '<w:fldSimple instr="DDE"> & https://example.test/file?x=1&y=2'
        root = document_xml(render_docx(replace(BASE, blocks=(OfficeBlock(text),))))
        self.assertEqual(paragraph_text(root.findall("w:body/w:p", NS)[1]), text)
        self.assertFalse(root.findall(".//w:fldSimple", NS))
        self.assertFalse(root.findall(".//w:hyperlink", NS))

    def test_mixed_runs_have_arabic_and_ltr_identifiers(self):
        text = 'رقم الطلب INV-2026 والبريد hello@example.test والمبلغ 120 SAR والنص <tag> "quote"'
        root = document_xml(render_docx(replace(BASE, blocks=(OfficeBlock(text),))))
        p = root.findall("w:body/w:p", NS)[1]
        self.assertEqual(paragraph_text(p), text)
        self.assertEqual(p.find("w:pPr/w:bidi", NS).get(f"{{{W_NS}}}val"), "1")
        ltr = "".join(paragraph_text(r) for r in p.findall(".//w:r", NS)
                      if r.find("w:rPr/w:rtl", NS).get(f"{{{W_NS}}}val") == "0")
        self.assertIn("INV-2026", ltr)
        self.assertIn("hello@example.test", ltr)
        self.assertIn("<tag>", ltr)
        self.assertIn('"quote"', ltr)

    def test_auto_and_explicit_paragraph_direction(self):
        blocks = (OfficeBlock("English first ثم عربي"), OfficeBlock("عربي", direction="ltr"),
                  OfficeBlock("English", direction="rtl"))
        root = document_xml(render_docx(replace(BASE, blocks=blocks)))
        paragraphs = root.findall("w:body/w:p", NS)[1:]
        self.assertEqual([p.find("w:pPr/w:bidi", NS).get(f"{{{W_NS}}}val")
                          for p in paragraphs], ["0", "0", "1"])
        self.assertTrue(all(p.find("w:pPr/w:jc", NS).get(f"{{{W_NS}}}val") == "start"
                            for p in paragraphs))

    def test_mixed_punctuation_uses_balanced_embeddings_without_enclosing_breaks(self):
        text = 'رموز <tag> & "quote".\nالتاريخ 2026-10-03\tالمبلغ 12.5% والطلب (INV-2026)'
        request = replace(BASE, blocks=(OfficeBlock(text),))
        p = document_xml(render_docx(request)).findall("w:body/w:p", NS)[1]
        self.assertEqual(request.blocks[0].text, text)
        self.assertEqual(paragraph_text(p), text)
        tokens = [node.text for node in p.findall(".//w:t", NS)]
        self.assertTrue(any('\u202a<tag> & "quote".\u202c' in token for token in tokens))
        self.assertTrue(any('\u202a2026-10-03\u202c' in token for token in tokens))
        for token in tokens:
            self.assertEqual(token.count("\u202a"), token.count("\u202c"))
            self.assertNotIn("\n", token)
            self.assertNotIn("\t", token)
        self.assertFalse(p.findall("w:dir", NS))
        english = document_xml(render_docx(replace(BASE, blocks=(
            OfficeBlock('English <tag> "quote".', direction="ltr"),
        )))).findall("w:body/w:p", NS)[1]
        self.assertNotIn("\u202a", ET.tostring(english, encoding="unicode"))

    def test_rejects_submitted_directional_embeddings_overrides_and_isolates(self):
        for char in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069":
            with self.subTest(char=repr(char)), self.assertRaises(InvalidOfficeInput) as caught:
                render_docx(replace(BASE, blocks=(OfficeBlock(f"private{char}ABC"),)))
            self.assertEqual(caught.exception.code, "unsupported_bidi_control")

    def test_package_is_deterministic_hashed_and_has_only_passive_parts(self):
        first, second = render_docx(BASE), render_docx(BASE)
        self.assertEqual(first, second)
        self.assertEqual(first.sha256, sha256(first.content).hexdigest())
        self.assertEqual(first.mime_type, MIME_TYPE)
        self.assertEqual(first.template_id, TEMPLATE_ID)
        with ZipFile(BytesIO(first.content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {"[Content_Types].xml", "_rels/.rels",
                "word/document.xml", "word/styles.xml", "word/_rels/document.xml.rels"})
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                root = ET.fromstring(archive.read(info.filename))
                for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                    self.assertNotIn("TargetMode", rel.attrib)
                    self.assertNotIn(":", rel.get("Target"))

    def test_title_heading_styles_black_and_complex_script_sizes(self):
        with ZipFile(BytesIO(render_docx(BASE).content)) as archive:
            styles = ET.fromstring(archive.read("word/styles.xml"))
        self.assertEqual(len(styles.findall("w:style", NS)), 3)
        for style in styles.findall("w:style", NS):
            self.assertEqual(style.find("w:rPr/w:color", NS).get(f"{{{W_NS}}}val"), "000000")
            self.assertEqual(style.find("w:rPr/w:sz", NS).attrib,
                             style.find("w:rPr/w:szCs", NS).attrib)
            self.assertIsNone(style.find("w:pPr/w:pBdr", NS))

    def test_rejects_wrong_types_without_private_text_in_errors(self):
        candidates = [None, replace(BASE, title=None), replace(BASE, blocks=[]),
                      replace(BASE, blocks=("private body",)),
                      replace(BASE, blocks=(OfficeBlock(None),))]
        for candidate in candidates:
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaises(InvalidOfficeInput) as caught:
                    render_docx(candidate)
                self.assertNotIn("private body", str(caught.exception))
                self.assertEqual(str(caught.exception), caught.exception.code)

    def test_rejects_blank_title_body_and_empty_blocks(self):
        for candidate in [replace(BASE, title=" \n"), replace(BASE, blocks=()),
                          replace(BASE, blocks=(OfficeBlock(" \t\n"),))]:
            with self.subTest(candidate=candidate), self.assertRaises(InvalidOfficeInput):
                render_docx(candidate)

    def test_rejects_unknown_template_kind_and_direction(self):
        candidates = [replace(BASE, template_id="custom"),
                      replace(BASE, blocks=(OfficeBlock("نص", "table"),)),
                      replace(BASE, blocks=(OfficeBlock("نص", direction="sideways"),))]
        for candidate in candidates:
            with self.assertRaises(InvalidOfficeInput):
                render_docx(candidate)

    def test_rejects_invalid_xml_controls_surrogates_and_noncharacters(self):
        for char in ("\x00", "\x08", "\x0b", "\x0c", "\x1f", "\ud800", "\ufffe", "\uffff"):
            for candidate in (replace(BASE, title=f"private{char}"),
                              replace(BASE, blocks=(OfficeBlock(f"private{char}"),))):
                with self.subTest(char=repr(char)):
                    with self.assertRaises(InvalidOfficeInput) as caught:
                        render_docx(candidate)
                    self.assertEqual(caught.exception.code, "invalid_xml_character")

    def test_accepts_unicode_emoji_and_diacritics_without_normalizing(self):
        text = "عَرَبِيّ 😀 e\u0301 ١٢٣"
        root = document_xml(render_docx(replace(BASE, blocks=(OfficeBlock(text),))))
        self.assertEqual(paragraph_text(root.findall("w:body/w:p", NS)[1]), text)

    def test_rejects_oversized_title_block_count_and_block_text(self):
        for candidate in (replace(BASE, title="أ" * (MAX_TITLE_CHARS + 1)),
                          replace(BASE, blocks=(OfficeBlock("أ"),) * (MAX_BLOCKS + 1)),
                          replace(BASE, blocks=(OfficeBlock("أ" * (MAX_BLOCK_CHARS + 1)),))):
            with self.assertRaises(InvalidOfficeInput):
                render_docx(candidate)

    def test_total_limit_counts_title_and_rejects_overflow(self):
        title = "ت"
        blocks = (OfficeBlock("أ" * MAX_BLOCK_CHARS),) * 3
        document = OfficeDocument(title, blocks + (OfficeBlock("ب" * (MAX_BLOCK_CHARS - 1)),))
        result = render_docx(document)
        root = document_xml(result)
        self.assertEqual(sum(len(paragraph_text(p)) for p in root.findall("w:body/w:p", NS)),
                         MAX_TEXT_CHARS)
        with self.assertRaises(InvalidOfficeInput):
            render_docx(replace(document, title="تت"))

    def test_rejects_multiline_or_oversized_headings(self):
        for text in ("", "قسم\nآخر", "قسم\tآخر", "أ" * (MAX_TITLE_CHARS + 1)):
            with self.assertRaises(InvalidOfficeInput):
                render_docx(replace(BASE, blocks=(OfficeBlock(text, "heading"),)))

    def test_output_failure_returns_no_partial_artifact(self):
        with (patch("platform_core.office_docx.MAX_OUTPUT_BYTES", 1),
              self.assertRaises(OfficeOutputLimitExceeded)):
            render_docx(BASE)

    def test_alternating_scripts_at_limit_preserve_content(self):
        text = "أA" * (MAX_BLOCK_CHARS // 2)
        root = document_xml(render_docx(replace(BASE, blocks=(OfficeBlock(text),) * 3)))
        self.assertEqual([paragraph_text(p) for p in root.findall("w:body/w:p", NS)[1:]],
                         [text] * 3)


if __name__ == "__main__":
    unittest.main()
