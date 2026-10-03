# Local Arabic Word executor

This experimental module formats supplied text into editable DOCX bytes. It is not
registered in the service catalog or wired to Telegram, storage, orders or payments.
It is not a qualified customer service yet.

`platform_core.office_docx.render_docx(OfficeDocument(...))` accepts an immutable
title, tuple of `OfficeBlock` values and the fixed `formal-ar-v1` template. Blocks
are paragraphs or one-level headings with auto/RTL/LTR paragraph direction.
Auto direction uses the first strong character, falling back to Arabic RTL.

```python
from platform_core.office_docx import OfficeBlock, OfficeDocument, render_docx

artifact = render_docx(OfficeDocument(
    title="تقرير العمل",
    blocks=(OfficeBlock("المقدمة", "heading"), OfficeBlock("النص الذي يرسله العميل.")),
))
# artifact.content is bytes; artifact.sha256 identifies those exact bytes.
```

The executor uses only Python's standard library. It creates native text, styles,
line breaks and tabs, with Letter portrait pages, one-inch margins and Arial.
There are no macros, fields, hyperlinks, media, external relationships or personal
metadata. Submitted URLs remain literal text. XML-like input is escaped, never
interpreted as document markup. Visible Unicode is preserved; CRLF/CR line endings become LF.
The same input produces the same ZIP bytes on the same Python/zlib toolchain.

For Latin runs in RTL paragraphs, the DOCX contains balanced Unicode LRE/PDF
formatting marks (U+202A/U+202C). This fixes the observed converter misordering of
angle brackets, quoted text, dates and percentages. Trailing whitespace stays
outside each embedding; embeddings never span a tab or explicit line break.
Original request strings are not mutated. Copied/extracted DOCX text includes the
invisible marks, so it is not byte-for-byte equal to the submitted text. Keep the
original request as the authoritative text. For logical comparison only, remove
U+202A/U+202C from extracted text. Input embeddings, overrides and isolates
(U+202A..U+202E and U+2066..U+2069) are rejected with `unsupported_bidi_control`;
this prevents submitted controls from escaping the formatter's embeddings.

Development bounds: title/heading 200 characters, 200 blocks, paragraph 10,000
characters, total title/body 40,000 characters and ZIP output 2 MiB. These are input
bounds, not advertised prices, performance promises or maximum rendered page counts.
Only blank paragraphs within a nonempty body are accepted. Unsupported templates,
types, directions, headings and XML 1.0 characters are rejected with a sanitized
`InvalidOfficeInput.code`. `OfficeOutputLimitExceeded` yields no partial artifact.
Unexpected faults propagate. A future channel boundary must classify/log sanitized
failures without text, handle storage/delivery separately and avoid payment capture
before an actual delivery receipt.

Local verification uses Python 3.12.14 and synthetic inputs. Eighteen unittest tests
also run under the existing pytest suite without new dependencies. Native package
visible-content preservation and ZIP checks pass. The mixed punctuation regression,
Arabic alignment and multipage layout pass on the inspected synthetic fixtures in
the bundled LibreOffice renderer. Python-docx open/edit/save/reopen also preserves
the fixture's visible content. These results do not qualify a paying customer
service or universal Word compatibility: real Microsoft Word desktop/mobile
editing and live bot delivery are not tested. The
[task report](../ENGINEERING/REPORTS/2026-10-03-OFFICE_DOCX.md) records
the exact scope and evidence. The canonical plan remains the existing
[roadmap](../ENGINEERING/MASTER_ROADMAP.md).
