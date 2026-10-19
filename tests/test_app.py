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
    assert any("reembolsos.md" in item.label for item in app.expander)
    assert any("30 dias" in item.value for item in app.text)
    assert any("Demonstração de recuperação" in item.value for item in app.info)
    next(button for button in app.button if button.label == "Limpar base e resposta").click()
    app.run()
    assert app.session_state["index"] is None
    assert app.session_state["result"] is None
