import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ragsearch import corpus
from ragsearch.retrieval import SearchIndex, read_document


@pytest.fixture
def corpus_source(tmp_path):
    catalog = {
        "name": "Teste local",
        "publisher": "Fonte de teste",
        "homepage": "https://cartilha.cert.br/",
        "index_url": "https://cartilha.cert.br/fasciculos/",
        "preferred_topics": ["backup"],
        "document_limit": 1,
    }
    (tmp_path / "catalog.json").write_text(json.dumps(catalog))
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
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Backup protects files from accidental loss.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return tmp_path, catalog, buffer.getvalue()


def test_import_records_provenance_preserves_pdf_and_supports_search(corpus_source, monkeypatch):
    root, catalog, pdf = corpus_source
    html = b"""<a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">License</a>
    <a href="backup/fasciculo-backup.pdf">Backup</a>"""
    expected_url = "https://cartilha.cert.br/fasciculos/backup/fasciculo-backup.pdf"
    requested = []

    def fetch(url, max_bytes=0):
        requested.append(url)
        return html if url == catalog["index_url"] else pdf

    monkeypatch.setattr(corpus, "_fetch", fetch)
    files = corpus.import_corpus(root)
    assert requested == [catalog["index_url"], expected_url]
    assert files == [("fasciculo-backup.pdf", pdf)]
    manifest = json.loads((root / "snapshot" / "manifest.json").read_text())
    assert manifest["license_url"] == "https://creativecommons.org/licenses/by-nc-nd/4.0/"
    assert manifest["documents"][0]["url"] == expected_url
    assert manifest["documents"][0]["sha256"] == hashlib.sha256(pdf).hexdigest()
    index = SearchIndex(read_document(*files[0]))
    assert "accidental loss" in index.search("backup")[0].chunk.text
    requested.clear()
    assert corpus.import_corpus(root) == files
    assert requested == []  # Reutiliza sem rede nem substituição.
    (root / "snapshot" / "pdfs" / files[0][0]).write_bytes(b"changed")
    with pytest.raises(corpus.CorpusError, match="alterada"):
        corpus.load_corpus(root)


def test_no_partial_snapshot_after_failed_pdf(corpus_source, monkeypatch):
    root, catalog, _ = corpus_source
    html = b"""<a href="https://creativecommons.org/licenses/by/4.0/">License</a>
    <a href="backup/fasciculo-backup.pdf">Backup</a>"""
    monkeypatch.setattr(
        corpus, "_fetch", lambda url, *args: html if url == catalog["index_url"] else b"not a PDF"
    )
    with pytest.raises(corpus.CorpusError, match="PDF"):
        corpus.import_corpus(root)
    assert not (root / "snapshot").exists()
    assert not list(root.glob(".import-*"))


def test_official_license_page_and_print_variants(corpus_source, monkeypatch):
    root, catalog, pdf = corpus_source
    index = b"""<a href="/cc/">License</a>
    <a href="backup/fasciculo-backup-alta.pdf">Print</a>
    <a href="backup/fasciculo-backup-grafica.pdf">Print</a>
    <a href="backup/fasciculo-backup.pdf">Web PDF</a>"""
    license_html = b'<a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC</a>'
    requested = []

    def fetch(url, max_bytes=0):
        requested.append(url)
        if url == catalog["index_url"]:
            return index
        if url == "https://cartilha.cert.br/cc/":
            return license_html
        return pdf

    monkeypatch.setattr(corpus, "_fetch", fetch)
    assert corpus.import_corpus(root) == [("fasciculo-backup.pdf", pdf)]
    manifest = json.loads((root / "snapshot" / "manifest.json").read_text())
    assert manifest["license_source_url"] == "https://cartilha.cert.br/cc/"
    assert len(requested) == 3
    assert not any("-alta.pdf" in url or "-grafica.pdf" in url for url in requested)


def test_no_license_blocks_distribution(corpus_source, monkeypatch):
    root, _, _ = corpus_source
    monkeypatch.setattr(corpus, "_fetch", lambda *args: b'<a href="fasciculo-backup.pdf">PDF</a>')
    with pytest.raises(corpus.CorpusError, match="Licença"):
        corpus.import_corpus(root)
    assert not (root / "snapshot").exists()


def test_missing_corpus_explains_how_to_import(tmp_path):
    with pytest.raises(corpus.CorpusError, match="uv run python -m ragsearch.corpus"):
        corpus.load_corpus(tmp_path)


def test_download_rejects_unofficial_hosts_before_network():
    with pytest.raises(corpus.CorpusError, match="oficial"):
        corpus._fetch("https://example.org/fasciculo-backup.pdf")


def test_app_missing_public_corpus_is_not_reported_as_loaded(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    original_load = corpus.load_corpus

    def missing():
        return original_load(tmp_path)

    monkeypatch.setattr(corpus, "load_corpus", missing)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py")).run()
    next(button for button in app.button if button.label == "Carregar base pública CERT.br").click()
    app.run()
    assert not app.exception
    assert any("ainda não foram importados" in error.value for error in app.error)
    assert app.session_state["index"] is None
