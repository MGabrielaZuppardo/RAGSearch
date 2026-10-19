import json

import httpx
import pytest

from ragsearch.generation import NO_EVIDENCE, GenerationError, generate_answer
from ragsearch.retrieval import Chunk, Hit

HITS = [Hit(Chunk("policy.pdf", "O prazo é de 30 dias.", 1, 2), 0.7)]


def test_generation_sends_retrieved_context_and_returns_citation():
    def handler(request):
        assert request.url == "https://api.openai.com/v1/chat/completions"
        data = json.loads(request.content)
        assert "policy.pdf, página 2" in data["messages"][1]["content"]
        assert "O prazo é de 30 dias." in data["messages"][1]["content"]
        assert data["messages"][-1]["content"] == "Qual o prazo?"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "O prazo é de 30 dias [1]."}}]}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        answer = generate_answer("Qual o prazo?", HITS, "test-key", client=client)
    assert answer == "O prazo é de 30 dias [1]."


@pytest.mark.parametrize("answer", ["Sem citações.", "Prazo de 30 dias [99].", ""])
def test_response_without_valid_source_is_not_presented(answer):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})
        )
    ) as client:
        with pytest.raises(GenerationError):
            generate_answer("Prazo?", HITS, "test-key", client=client)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_api_failures_are_safe_and_actionable(status):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json={"error": "sensitive provider details"})
        )
    ) as client:
        with pytest.raises(GenerationError) as error:
            generate_answer("Prazo?", HITS, "test-key", client=client)
    assert str(status) in str(error.value)
    assert "test-key" not in str(error.value)
    assert "sensitive" not in str(error.value)


def test_no_context_does_not_call_provider():
    def fail_on_request(_):
        pytest.fail("A API não deve ser chamada sem evidências.")

    with httpx.Client(transport=httpx.MockTransport(fail_on_request)) as client:
        assert generate_answer("Prazo?", [], "", client=client) == NO_EVIDENCE
