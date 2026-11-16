from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import questions
from app.answer_contract import DraftAnswer
from app.retrieval import RetrievalResponse, RetrievedChunk


def make_client():
    app = FastAPI()
    app.include_router(questions.router)
    return TestClient(app)


def chunk(chunk_id, **extra):
    return RetrievedChunk(
        chunk_id=chunk_id, document_id="doc", index_id="idx", filename="f.md",
        content_hash="h", start=0, end=10, text="E47 means the grinder is blocked.",
        **extra,
    )


def retrieval(matches):
    return RetrievalResponse(
        question="What does E47 mean?", document_ids=["doc"], top_k=3, matches=matches,
        retrievers=["dense", "bm25"], candidate_depth=50, rrf_k=60,
        weights={"dense": 1.0, "bm25": 1.0},
    )


REQUEST = {"question": "What does E47 mean?", "document_ids": ["doc"],
           "retrievers": ["dense", "bm25"]}


def test_answer_keeps_ranks_and_accepts_a_chunk_without_distance(monkeypatch):
    monkeypatch.setattr(questions, "retrieve_chunks", lambda request: retrieval(
        [chunk("c1", distance=None, retriever_ranks={"bm25": 1})]
    ))
    monkeypatch.setattr(questions, "generate_answer", lambda **kwargs: (
        DraftAnswer(status="answered", answer="Blocked grinder.", citation_ids=["c1"]),
        "test-model",
    ))

    body = make_client().post("/api/questions", json=REQUEST).json()

    assert body["status"] == "answered"
    assert body["citations"][0]["distance"] is None
    assert body["citations"][0]["retriever_ranks"] == {"bm25": 1}
    assert body["retrieval"]["retrievers"] == ["dense", "bm25"]
    assert body["retrieval"]["candidate_depth"] == 50


def test_no_evidence_still_reports_the_retrieval_summary(monkeypatch):
    monkeypatch.setattr(questions, "retrieve_chunks", lambda request: retrieval([]))

    def unexpected(**kwargs):
        raise AssertionError("The model should not be called.")

    monkeypatch.setattr(questions, "generate_answer", unexpected)

    body = make_client().post("/api/questions", json=REQUEST).json()

    assert body["status"] == "insufficient_evidence"
    assert body["citations"] == []
    assert body["retrieval"]["rrf_k"] == 60


def test_empty_retriever_selection_is_rejected():
    response = make_client().post(
        "/api/questions", json={**REQUEST, "retrievers": []}
    )
    assert response.status_code == 422