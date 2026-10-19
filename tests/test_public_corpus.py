"""Smoke tests sobre os PDFs reais versionados; não usam rede nem modelos de IA."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ragsearch.corpus import load_corpus
from ragsearch.retrieval import SearchIndex, read_document


@pytest.fixture(scope="module")
def public_index():
    files = load_corpus()
    assert len(files) == 5
    documents = []
    for filename, content in files:
        extracted = read_document(filename, content)
        assert sum(len(doc.text) for doc in extracted) > 1000, filename
        documents.extend(extracted)
    return SearchIndex(documents)


@pytest.mark.parametrize(
    ("question", "source", "page", "evidence"),
    [
        (
            "Como conferir um boleto antes de pagar?",
            "fasciculo-golpes-evite-fraudes.pdf",
            13,
            "CNPJ",
        ),
        (
            "O que fazer antes de descartar um celular?",
            "fasciculo-protecao-de-dados.pdf",
            14,
            "Restaure as configurações",
        ),
    ],
)
def test_real_documents_retrieve_answer_and_page(public_index, question, source, page, evidence):
    hits = public_index.search(question)
    assert hits
    assert hits[0].chunk.source == source
    assert hits[0].chunk.page == page
    assert evidence in hits[0].chunk.text


def test_unrelated_question_has_no_lexical_evidence(public_index):
    assert public_index.search("Qual é a capital da Noruega?") == []


def test_public_corpus_in_interface(monkeypatch):
    monkeypatch.delenv("RAG_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=15).run()
    next(button for button in app.button if button.label == "Carregar base pública CERT.br").click()
    app.run()
    assert not app.exception
    assert app.session_state["base_kind"] == "certbr"
    assert app.metric[0].value == "5"
    app.text_input[0].set_value("Como conferir um boleto antes de pagar?")
    next(button for button in app.button if button.label == "Consultar documentos").click()
    app.run()
    assert not app.exception
    assert any(
        "fasciculo-golpes-evite-fraudes.pdf · página 13" in item.label for item in app.expander
    )
    assert any("CNPJ" in item.value for item in app.text)
