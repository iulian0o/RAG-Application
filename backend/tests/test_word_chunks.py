from contextlib import contextmanager
from threading import Lock

import pytest
from fastapi import HTTPException

from app import word_chunks


@pytest.fixture
def stored_document(monkeypatch):
    row = {
        "id": "doc-1",
        "filename": "guide.txt",
        "content": "Phone phone",
        "current_hash": "hash-1",
        "index_id": "index-1",
        "indexed_hash": "hash-1",
        "model_name": word_chunks.MODEL_NAME,
        "chunk_count": 1,
    }

    class Connection:
        def execute(self, sql, parameters):
            return self

        def fetchall(self):
            return [row]

    @contextmanager
    def fake_database():
        yield Connection()

    monkeypatch.setattr(word_chunks, "database", fake_database)
    monkeypatch.setattr(word_chunks, "index_write_lock", Lock())
    return row


def metadata():
    return {
        "document_id": "doc-1",
        "index_id": "index-1",
        "content_hash": "hash-1",
        "chunk_index": 0,
        "start": 0,
        "end": 11,
    }


def test_reader_filters_to_active_indexes(monkeypatch, stored_document):
    captured = {}

    class Collection:
        def get(self, **kwargs):
            captured.update(kwargs)
            return {
                "ids": ["index-1:0"],
                "documents": ["Phone phone"],
                "metadatas": [metadata()],
            }

    monkeypatch.setattr(word_chunks, "get_collection", lambda: Collection())

    chunks = word_chunks.read_word_chunks(["doc-1"])

    assert captured["where"] == {"index_id": {"$in": ["index-1"]}}
    assert chunks[0].text == "Phone phone"
    assert word_chunks.index_write_lock.locked() is False


def test_missing_chunks_are_rejected(monkeypatch, stored_document):
    class Collection:
        def get(self, **kwargs):
            return {"ids": [], "documents": [], "metadatas": []}

    monkeypatch.setattr(word_chunks, "get_collection", lambda: Collection())

    with pytest.raises(HTTPException) as error:
        word_chunks.read_word_chunks(["doc-1"])

    assert error.value.status_code == 503
    assert word_chunks.index_write_lock.locked() is False


def test_outdated_index_is_rejected(stored_document):
    stored_document["indexed_hash"] = "old-hash"

    with pytest.raises(HTTPException) as error:
        word_chunks.read_word_chunks(["doc-1"])

    assert error.value.status_code == 409


def test_unselected_chunk_is_rejected(stored_document):
    invalid = metadata()
    invalid["document_id"] = "other-document"

    with pytest.raises(ValueError, match="unselected"):
        word_chunks.validate_chunk(
            "index-1:0",
            "Phone phone",
            invalid,
            {"doc-1": stored_document},
        )


def test_changed_chunk_text_is_rejected(stored_document):
    with pytest.raises(ValueError, match="source"):
        word_chunks.validate_chunk(
            "index-1:0",
            "Different",
            metadata(),
            {"doc-1": stored_document},
        )


def test_busy_index_returns_conflict(monkeypatch):
    lock = Lock()
    lock.acquire()
    monkeypatch.setattr(word_chunks, "index_write_lock", lock)

    try:
        with pytest.raises(HTTPException) as error:
            word_chunks.read_word_chunks(["doc-1"])
        assert error.value.status_code == 409
    finally:
        lock.release()