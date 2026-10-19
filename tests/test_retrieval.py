from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ragsearch.evaluate import evaluate
from ragsearch.retrieval import Document, SearchIndex, chunk_documents, read_document


def test_pdf_extracts_text_and_keeps_page_reference():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Backups retained for 90 days.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    docs = read_document("policy.pdf", buffer.getvalue())
    hits = SearchIndex(docs).search("backups")
    assert hits[0].chunk.source == "policy.pdf"
    assert hits[0].chunk.page == 1
    assert "90 days" in hits[0].chunk.text


def test_scanned_pdf_reports_need_for_ocr():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(ValueError, match="OCR"):
        read_document("scan.pdf", buffer.getvalue())


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes.exe", b"data"),
        ("notes.txt", b""),
        ("notes.md", b"\xff"),
        ("notes.pdf", b"not a pdf"),
        ("notes.txt", b" " * 20),
    ],
)
def test_invalid_documents_are_rejected(name, content):
    with pytest.raises(ValueError):
        read_document(name, content)


def test_utf8_markdown_and_safe_filename():
    docs = read_document("../notas.md", "\ufeffPolítica de retenção".encode())
    assert docs == [Document("notas.md", "Política de retenção")]


def test_chunks_keep_overlap_and_page_without_losing_words():
    chunks = chunk_documents([Document("manual.pdf", "a b c d e f g h", 2)], 4, 1)
    assert [chunk.text for chunk in chunks] == ["a b c d", "d e f g", "g h"]
    assert all(chunk.page == 2 for chunk in chunks)


def test_search_ranks_relevant_document_and_abstains_on_unknown_terms():
    index = SearchIndex(
        [
            Document("financeiro.md", "Reembolso solicitado em até 30 dias com nota fiscal."),
            Document("seguranca.md", "Backups são mantidos por 90 dias em armazenamento seguro."),
        ]
    )
    assert index.search("reembolso nota fiscal")[0].chunk.source == "financeiro.md"
    assert index.search("astronomia planetas jupiter") == []
    with pytest.raises(ValueError):
        index.search(" ")


def test_synthetic_retrieval_benchmark():
    report = evaluate()
    assert report["total"] == 6
    assert report["passed"] == report["total"]
