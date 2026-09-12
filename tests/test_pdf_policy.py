"""Reject active document features before any PDF merge or delivery."""

from io import BytesIO

import pytest
from platform_core.pdf_isolation import merge_pdfs_isolated
from platform_core.pdf_merge import InvalidPDF, merge_pdfs
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject


def pdf_with(feature: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if feature == "javascript":
        writer.add_js("app.alert('hello')")
    elif feature == "attachment":
        writer.add_attachment(filename="payload.txt", data=b"payload")
    elif feature == "annotation":
        writer.pages[0][NameObject("/Annots")] = ArrayObject()
    elif feature == "benign_title":
        writer.add_metadata({"/Title": "Guide to /JavaScript text"})
    output = BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


@pytest.mark.parametrize("feature", ["javascript", "attachment", "annotation"])
def test_pdf_policy_rejects_active_features_in_parser_and_container_child(feature):
    documents = [pdf_with("benign_title"), pdf_with(feature)]
    with pytest.raises(InvalidPDF, match="unsupported active content"):
        merge_pdfs(documents)
    with pytest.raises(InvalidPDF):
        merge_pdfs_isolated(documents)


def test_pdf_policy_does_not_reject_inert_text_containing_feature_name():
    output = merge_pdfs([pdf_with("benign_title"), pdf_with("benign_title")])
    assert len(PdfReader(BytesIO(output), strict=True).pages) == 2
