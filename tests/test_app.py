from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_question_sources_and_reset(monkeypatch):
    monkeypatch.delenv("RAG_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))
    app.run()
    assert not app.exception
    next(button for button in app.button if button.label == "Experimentar base de exemplo").click()
    app.run()
    assert not app.exception
    app.text_input[0].set_value("Qual é o prazo para solicitar reembolso?")
    next(button for button in app.button if button.label == "Consultar documentos").click()
    app.run()
    assert not app.exception
    assert any("Reembolsos" in item.label for item in app.expander)
    assert any("reembolsos.md" in item.value for item in app.caption)
    assert any("30 dias" in item.value for item in app.text)
    assert any("trechos originais" in item.value for item in app.info)
    next(button for button in app.button if button.label == "Limpar base e resposta").click()
    app.run()
    assert app.session_state["index"] is None
    assert app.session_state["result"] is None


def test_base_context_suggestions_and_switch_after_no_results(monkeypatch):
    monkeypatch.delenv("RAG_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=15).run()
    next(button for button in app.button if button.label == "Começar com o CERT.br").click()
    app.run()
    assert not app.exception
    assert any(item.value == "Segurança digital · CERT.br" for item in app.subheader)
    assert "reembolso" not in app.text_input[0].proto.placeholder
    suggestion = "Como conferir um boleto antes de pagar?"
    next(button for button in app.button if button.label == suggestion).click()
    app.run()
    assert app.text_input[0].value == suggestion
    assert app.session_state["result"] is None
    # Reproduz o caso de uma pergunta de reembolso enviada à base de segurança.
    app.text_input[0].set_value("Qual é o prazo para solicitar reembolso?")
    next(button for button in app.button if button.label == "Consultar documentos").click()
    app.run()
    assert not app.exception
    assert app.session_state["result"]["hits"] == []
    assert any("nesta base" in item.value for item in app.warning)
    next(button for button in app.button if button.label == "Trocar para a base de exemplo").click()
    app.run()
    assert not app.exception
    assert app.session_state["base_kind"] == "example"
    assert app.session_state["result"] is None
    assert app.text_input[0].value == ""
    assert "reembolso" in app.text_input[0].proto.placeholder
    assert not any(button.label == suggestion for button in app.button)
    next(
        button
        for button in app.button
        if button.label == "Qual é o prazo para solicitar reembolso?"
    ).click()
    app.run()
    next(button for button in app.button if button.label == "Consultar documentos").click()
    app.run()
    assert not app.exception
    assert any("30 dias" in item.value for item in app.text)
