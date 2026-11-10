import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import words
from app.word_chunks import WordChunk


def make_chunk(document_id, index_id, position, text):
    return WordChunk(
        chunk_id=f"{index_id}:{position}",
        document_id=document_id,
        index_id=index_id,
        filename=f"{document_id}.txt",
        content_hash=f"hash-{document_id}",
        chunk_index=position,
        start=0,
        end=len(text),
        text=text,
    )


@pytest.fixture
def client(monkeypatch):
    chunks = [
        make_chunk("doc-1", "index-1", 0, "Phone phone ERR-401"),
        make_chunk("doc-1", "index-1", 1, "Phone billing"),
        make_chunk("doc-2", "index-2", 0, "Secret phone"),
    ]

    def fake_read(document_ids):
        return [
            chunk for chunk in chunks
            if chunk.document_id in document_ids
        ]

    monkeypatch.setattr(words, "read_word_chunks", fake_read)

    app = FastAPI()
    app.include_router(words.router)

    with TestClient(app) as test_client:
        yield test_client


def test_vocabulary_counts_occurrences_and_distinct_chunks(client):
    response = client.post(
        "/api/words/vocabulary",
        json={"document_ids": ["doc-1"]},
    )

    assert response.status_code == 200
    result = response.json()

    assert result["total_chunks"] == 2
    assert result["total_occurrences"] == 5
    assert result["words"][0] == {
        "word": "phone",
        "occurrences": 3,
        "chunk_count": 2,
    }
    assert "secret" not in [word["word"] for word in result["words"]]


def test_vocabulary_pagination_preserves_totals(client):
    response = client.post(
        "/api/words/vocabulary",
        json={"document_ids": ["doc-1"], "offset": 1, "limit": 1},
    )

    result = response.json()
    assert result["total_words"] == 3
    assert len(result["words"]) == 1
    assert result["words"][0]["word"] == "billing"


def test_word_lookup_returns_per_chunk_counts(client):
    response = client.post(
        "/api/words/chunks",
        json={"document_ids": ["doc-1"], "word": "PHONE"},
    )

    result = response.json()
    assert result["word"] == "phone"
    assert result["occurrences"] == 3
    assert result["chunk_count"] == 2
    assert [
        match["occurrences"] for match in result["matches"]
    ] == [2, 1]


def test_missing_word_returns_an_empty_result(client):
    response = client.post(
        "/api/words/chunks",
        json={"document_ids": ["doc-1"], "word": "absent"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["occurrences"] == 0
    assert result["matches"] == []


def test_question_reports_present_absent_and_repeated_words(client):
    response = client.post(
        "/api/words/question",
        json={
            "document_ids": ["doc-1"],
            "question": "PHONE phone locked out ERR-401",
        },
    )

    result = response.json()
    assert result["absent"] == ["locked", "out"]
    assert [word["word"] for word in result["present"]] == [
        "phone",
        "err-401",
    ]
    assert result["present"][0]["question_occurrences"] == 2
    assert result["present"][0]["occurrences"] == 3

    chunk_ids = [chunk["chunk_id"] for chunk in result["chunks"]]
    assert len(chunk_ids) == len(set(chunk_ids)) == 2


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/vocabulary", {"document_ids": []}),
        ("/vocabulary", {"document_ids": [" "]}),
        ("/vocabulary", {"document_ids": ["doc-1"], "limit": 0}),
        ("/chunks", {"document_ids": ["doc-1"], "word": "two words"}),
        ("/question", {"document_ids": ["doc-1"], "question": "!!!"}),
    ],
)
def test_invalid_requests_return_422(client, path, payload):
    response = client.post(f"/api/words{path}", json=payload)
    assert response.status_code == 422


def test_index_errors_are_exposed_to_the_frontend(client, monkeypatch):
    def busy(document_ids):
        raise HTTPException(409, "An index operation is running.")

    monkeypatch.setattr(words, "read_word_chunks", busy)

    response = client.post(
        "/api/words/vocabulary",
        json={"document_ids": ["doc-1"]},
    )

    assert response.status_code == 409


def test_each_request_reads_current_chunks(client, monkeypatch):
    first = client.post(
        "/api/words/chunks",
        json={"document_ids": ["doc-1"], "word": "phone"},
    )
    assert first.json()["occurrences"] == 3

    monkeypatch.setattr(
        words,
        "read_word_chunks",
        lambda document_ids: [
            make_chunk("doc-1", "rebuilt-index", 0, "Billing only")
        ],
    )

    second = client.post(
        "/api/words/chunks",
        json={"document_ids": ["doc-1"], "word": "phone"},
    )

    assert second.json()["occurrences"] == 0
    assert second.json()["index_ids"] == ["rebuilt-index"]