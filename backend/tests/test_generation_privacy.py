import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import Request

from app import generation, questions
from app.redaction import RedactionError
from app.retrieval import RetrievalRequest, RetrievalResponse, RetrievedChunk
from app.traces import TraceRecord


EMAIL = "synthetic@example.test"
CHUNK_ID = "index-a:0"


@pytest.fixture
def traced_question(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    request = RetrievalRequest(
        question=f"Which address is listed for {EMAIL}?",
        document_ids=["document-a"],
    )
    text = f"The test contact is {EMAIL}."
    chunk = RetrievedChunk(
        chunk_id=CHUNK_ID,
        document_id="document-a",
        index_id="index-a",
        filename="synthetic.md",
        content_hash="test-hash",
        start=0,
        end=len(text),
        text=text,
    )
    response = RetrievalResponse(
        question=request.question,
        document_ids=request.document_ids,
        index_ids=["index-a"],
        top_k=request.top_k,
        matches=[chunk],
    )
    monkeypatch.setattr(questions, "retrieve_chunks", lambda _: response)
    trace = TraceRecord(operation="question")
    http_request = Request({"type": "http", "state": {"trace": trace}})
    return request, http_request, trace


@pytest.fixture
def fake_provider(monkeypatch):
    def install(raw_output):
        payloads = []

        def generate_content(*, model, contents, config):
            payloads.append(json.loads(contents))
            return SimpleNamespace(text=raw_output, usage_metadata=None)

        @contextmanager
        def client(**_):
            yield SimpleNamespace(
                models=SimpleNamespace(generate_content=generate_content),
            )

        monkeypatch.setattr(generation.genai, "Client", client)
        return payloads

    return install


def test_ask_records_counts_without_personal_data(traced_question, fake_provider):
    request, http_request, trace = traced_question
    payloads = fake_provider(json.dumps({
        "status": "answered",
        "answer": "The listed address is [EMAIL_1].",
        "citation_ids": [CHUNK_ID],
    }))

    answer = questions.ask_question(request, http_request)

    assert [citation.chunk_id for citation in answer.citations] == [CHUNK_ID]
    assert payloads == [{
        "question": "Which address is listed for [EMAIL_1]?",
        "evidence": [{"chunk_id": CHUNK_ID, "text": "The test contact is [EMAIL_1]."}],
    }]
    serialized = trace.model_dump_json()
    assert EMAIL not in serialized
    assert "[EMAIL_1]" not in serialized
    saved = TraceRecord.model_validate_json(serialized)
    assert saved.outcome == "answered"
    assert saved.llm_calls == 1
    assert saved.redaction.model_dump() == {
        "policy_version": "v1",
        "counts_by_entity_type": {"EMAIL": 1},
    }


def test_redaction_failure_blocks_before_creating_provider_client(
    monkeypatch, traced_question,
):
    request, http_request, trace = traced_question

    def fail_redaction(self, text):
        raise RedactionError("Synthetic redaction failure")

    def unexpected_client(**kwargs):
        pytest.fail("A failed redactor must prevent Gemini client creation.")

    monkeypatch.setattr(generation.RedactionSession, "redact", fail_redaction)
    monkeypatch.setattr(generation.genai, "Client", unexpected_client)

    with pytest.raises(generation.RedactionBlocked):
        questions.ask_question(request, http_request)

    assert trace.outcome == "blocked"
    assert trace.error_code == "redaction_failed"
    assert trace.llm_calls == 0
    assert trace.redaction is None


def test_invalid_provider_output_has_distinct_trace_outcome(
    traced_question, fake_provider,
):
    request, http_request, trace = traced_question
    payloads = fake_provider("invalid JSON")

    with pytest.raises(generation.InvalidModelOutput):
        questions.ask_question(request, http_request)

    assert len(payloads) == 1
    assert trace.outcome == "invalid_output"
    assert trace.error_code == "invalid_model_output"
    assert trace.llm_calls == 1
    assert trace.redaction.counts_by_entity_type == {"EMAIL": 1}
