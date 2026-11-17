"""The shared retrieval service with a fake database and a fake Chroma collection (no model, no files)."""
from contextlib import contextmanager
from threading import Lock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import bm25, retrieval, snapshot, word_chunks
from app.embeddings import MODEL_NAME
from app.retrieval import RetrievalRequest, retrieve_chunks

TEXTS = {
    "doc-a": [
        "Error E47 means the grinder is blocked by a foreign object such as a stone.",
        "Descale the machine regularly to remove limescale from the heater.",
        "The water tank holds 1.8 litres and has a filter holder.",
    ],
    "doc-b": [
        "A raven delivered a sealed message to the castle at dawn.",
        "The baker kneaded the dough and baked bread in the oven.",
    ],
}

# Fake embedding: a 2-d vector per chunk text and per question. Smaller distance = closer.
VECTORS = {
    "descaling question": {
        "doc-a": [5.0, 2.0, 4.0], "doc-b": [6.0, 3.0],     # chunk distances for this question
    },
}


class World:
    def __init__(self):
        self.documents, self.chunks = {}, {}
        self.distances = {}                                # question -> {chunk_id: distance}
        self.lock = Lock()

    def add(self, doc_id, texts=None, index_id=None, filename=None):
        texts = texts or TEXTS[doc_id]
        content = "".join(texts)
        index_id = index_id or f"idx-{doc_id}-1"
        self.documents[doc_id] = {
            "id": doc_id, "filename": filename or f"{doc_id}.txt", "content": content,
            "current_hash": f"hash-{doc_id}", "index_id": index_id, "indexed_hash": f"hash-{doc_id}",
            "model_name": MODEL_NAME, "chunk_count": len(texts),
        }
        start = 0
        for number, text in enumerate(texts):
            self.chunks[f"{index_id}:{number}"] = (text, {
                "document_id": doc_id, "index_id": index_id, "content_hash": f"hash-{doc_id}",
                "filename": f"{doc_id}.txt", "chunk_index": number, "start": start, "end": start + len(text),
            })
            start += len(text)

    def rebuild(self, doc_id):
        old = self.documents[doc_id]["index_id"]
        self.chunks = {k: v for k, v in self.chunks.items() if not k.startswith(old + ":")}
        self.add(doc_id, index_id=old + "-new")

    def delete(self, doc_id):
        old = self.documents.pop(doc_id)["index_id"]
        self.chunks = {k: v for k, v in self.chunks.items() if not k.startswith(old + ":")}


@pytest.fixture
def world(monkeypatch):
    w = World()
    w.add("doc-a")
    w.add("doc-b")

    class Connection:
        def execute(self, sql, parameters):
            self.rows = [w.documents[i] for i in parameters if i in w.documents]
            return self

        def fetchall(self):
            return self.rows

    @contextmanager
    def fake_database():
        yield Connection()

    class Collection:
        def get(self, where, include):
            wanted = set(where["index_id"]["$in"])
            keep = [(k, v) for k, v in w.chunks.items() if v[1]["index_id"] in wanted]
            return {"ids": [k for k, _ in keep], "documents": [v[0] for _, v in keep], "metadatas": [v[1] for _, v in keep]}

        def query(self, query_embeddings, n_results, where, include):
            wanted = set(where["index_id"]["$in"])
            distances = w.distances[tuple(query_embeddings[0])]
            keep = [(k, v) for k, v in w.chunks.items() if v[1]["index_id"] in wanted]
            keep.sort(key=lambda kv: distances.get(kv[0], 9.0))
            keep = keep[:n_results]
            return {
                "ids": [[k for k, _ in keep]], "documents": [[v[0] for _, v in keep]],
                "metadatas": [[v[1] for _, v in keep]], "distances": [[distances.get(k, 9.0) for k, _ in keep]],
            }

    def fake_embed(texts):
        return [[float(len(texts[0]))]]

    def set_distances(question, by_text_start):
        vector = (float(len(question)),)
        w.distances[vector] = {
            cid: d for cid, (text, _) in w.chunks.items() for start, d in by_text_start.items() if text.startswith(start)
        }

    w.set_distances = set_distances
    collection = Collection()
    monkeypatch.setattr(snapshot, "database", fake_database)
    monkeypatch.setattr(snapshot, "get_collection", lambda: collection)
    monkeypatch.setattr(retrieval, "get_collection", lambda: collection)
    monkeypatch.setattr(retrieval, "embed_texts", fake_embed)
    monkeypatch.setattr(retrieval, "index_write_lock", w.lock)
    monkeypatch.setattr(word_chunks, "index_write_lock", w.lock)
    bm25.clear_cache()
    yield w
    bm25.clear_cache()


QUESTION = "What does error E47 mean?"
DISTANCES = {   # dense prefers the descaling chunk, not the E47 one (the failure BM25 should fix)
    "Descale": 0.30, "The water tank": 0.35, "Error E47": 0.50, "A raven": 0.80, "The baker": 0.90,
}


def request(**kw):
    return RetrievalRequest(question=QUESTION, document_ids=["doc-a", "doc-b"], **kw)


def test_dense_only_is_the_default_and_keeps_v2_behaviour(world):
    world.set_distances(QUESTION, DISTANCES)
    response = retrieve_chunks(request(top_k=3))

    assert response.index_ids == ["idx-doc-a-1", "idx-doc-b-1"]
    assert response.retrievers == ["dense"]
    assert response.candidate_depth == 3
    assert [m.text[:7] for m in response.matches] == ["Descale", "The wat", "Error E"]
    assert [m.distance for m in response.matches] == [0.30, 0.35, 0.50]
    assert [m.fused_rank for m in response.matches] == [1, 2, 3]
    assert all(m.retriever_ranks.keys() == {"dense"} for m in response.matches)
    assert response.matches[0].chunk_id == "idx-doc-a-1:1"
    assert response.candidates is None


def test_bm25_only_finds_the_identifier_dense_ranked_third(world):
    response = retrieve_chunks(request(retrievers=["bm25"], top_k=3))

    top = response.matches[0]
    assert top.text.startswith("Error E47")
    assert top.distance is None
    assert top.retriever_ranks == {"bm25": 1}
    assert "e47" in top.evidence["bm25"]["matched_terms"]


def test_hybrid_rrf_promotes_the_chunk_both_retrievers_like(world):
    world.set_distances(QUESTION, DISTANCES)
    response = retrieve_chunks(request(retrievers=["dense", "bm25"], top_k=3, include_candidates=True))

    first = response.matches[0]
    assert first.text.startswith("Error E47")                     # dense rank 3 + bm25 rank 1 beats dense rank 1 alone
    assert first.retriever_ranks == {"dense": 3, "bm25": 1}
    assert first.distance == 0.50 and "bm25" in first.evidence and "dense" in first.evidence
    assert response.candidate_depth == 50
    assert response.candidate_counts["dense"] == 5
    assert [c.rank for c in response.candidates["bm25"]][:1] == [1]
    ids = [m.chunk_id for m in response.matches]
    assert len(ids) == len(set(ids))                              # deduplicated


def test_weighted_rrf_can_change_the_top_result(world):
    world.set_distances(QUESTION, DISTANCES)
    plain = retrieve_chunks(request(retrievers=["dense", "bm25"], top_k=2))
    dense_heavy = retrieve_chunks(request(retrievers=["dense", "bm25"], top_k=2, weights={"bm25": 0.01}))

    assert plain.matches[0].text.startswith("Error E47")            # plain: dense rank 3 + bm25 rank 1 wins
    assert dense_heavy.matches[0].text.startswith("Descale")        # a nearly silent BM25: dense rank 1 wins
    assert dense_heavy.weights == {"dense": 1.0, "bm25": 0.01}


def test_distance_is_kept_only_for_chunks_dense_found(world):
    world.set_distances(QUESTION, DISTANCES)
    response = retrieve_chunks(request(retrievers=["dense", "bm25"], top_k=2, candidate_depth=2))
    bm25_only = [m for m in response.matches if "dense" not in m.retriever_ranks]

    assert response.candidate_depth == 2
    assert all(m.distance is None for m in bm25_only) or bm25_only == []
    assert all((m.distance is not None) == ("dense" in m.retriever_ranks) for m in response.matches)


def test_results_stay_within_the_selected_documents(world):
    world.set_distances(QUESTION, DISTANCES)
    response = retrieve_chunks(RetrievalRequest(question=QUESTION, document_ids=["doc-b"],
                                                retrievers=["dense", "bm25"], top_k=5))
    assert {m.document_id for m in response.matches} == {"doc-b"}


def test_rebuild_cannot_return_old_chunks(world):
    world.set_distances(QUESTION, DISTANCES)
    retrieve_chunks(request(retrievers=["bm25"]))                  # fills the BM25 cache for the old index
    world.rebuild("doc-a")
    response = retrieve_chunks(request(retrievers=["bm25"], top_k=5))

    assert response.matches
    assert all(m.index_id != "idx-doc-a-1" for m in response.matches)
    assert any(m.index_id == "idx-doc-a-1-new" for m in response.matches)


def test_deleted_document_is_404_and_does_not_leak_through_the_cache(world):
    retrieve_chunks(request(retrievers=["bm25"]))
    world.delete("doc-b")

    with pytest.raises(HTTPException) as error:
        retrieve_chunks(request(retrievers=["bm25"]))
    assert error.value.status_code == 404

    remaining = retrieve_chunks(RetrievalRequest(question=QUESTION, document_ids=["doc-a"], retrievers=["bm25"]))
    assert {m.document_id for m in remaining.matches} == {"doc-a"}


def test_stale_and_missing_indexes_are_409(world):
    world.documents["doc-a"]["indexed_hash"] = "older"
    with pytest.raises(HTTPException) as stale:
        retrieve_chunks(request(retrievers=["bm25"]))
    assert stale.value.status_code == 409 and "outdated" in stale.value.detail

    world.documents["doc-a"]["indexed_hash"] = "hash-doc-a"
    world.documents["doc-b"]["index_id"] = None
    with pytest.raises(HTTPException) as missing:
        retrieve_chunks(request(retrievers=["dense"]))
    assert missing.value.status_code == 409


def test_chunk_that_does_not_match_its_source_is_rejected(world):
    key = "idx-doc-a-1:0"
    text, metadata = world.chunks[key]
    world.chunks[key] = (text.replace("E47", "E48"), metadata)

    with pytest.raises(HTTPException) as error:
        retrieve_chunks(request(retrievers=["bm25"]))
    assert error.value.status_code == 503


def test_graph_is_a_clear_error_until_it_is_registered(world, monkeypatch):
    with pytest.raises(HTTPException) as error:
        retrieve_chunks(request(retrievers=["dense", "graph"]))
    assert error.value.status_code == 409 and "graph" in error.value.detail

    def fake_graph(query):
        chunk = query.snapshot.read_chunks()[0]
        return [retrieval.Candidate(chunk=chunk, graph_paths=[{"entities": ["Aurora Reports"], "edges": []}])]

    monkeypatch.setitem(retrieval.RETRIEVERS, "graph", fake_graph)
    world.set_distances(QUESTION, DISTANCES)
    response = retrieve_chunks(request(retrievers=["graph", "bm25"], top_k=5))
    graph_only = [m for m in response.matches if m.retriever_ranks.get("graph") and "bm25" not in m.retriever_ranks]

    assert any(m.graph_paths for m in response.matches)
    assert all(m.distance is None for m in graph_only)


def test_busy_index_lock_is_409(world):
    world.lock.acquire()
    try:
        with pytest.raises(HTTPException) as error:
            retrieve_chunks(request())
        assert error.value.status_code == 409
    finally:
        world.lock.release()


def test_lock_is_released_after_success_and_failure(world):
    world.documents["doc-a"]["indexed_hash"] = "older"
    with pytest.raises(HTTPException):
        retrieve_chunks(request())
    assert world.lock.acquire(blocking=False)
    world.lock.release()


@pytest.mark.parametrize(
    "extra",
    [
        {"retrievers": []},
        {"retrievers": ["magic"]},
        {"top_k": 0},
        {"top_k": 21},
        {"candidate_depth": 2, "top_k": 5},
        {"candidate_depth": 201},
        {"weights": {"graph": 2.0}},
        {"weights": {"dense": 0}},
        {"weights": {"dense": float("nan")}},
        {"rrf_k": 0},
        {"unknown": 1},
    ],
)
def test_invalid_requests_are_rejected(extra):
    with pytest.raises(ValidationError):
        RetrievalRequest(question="q", document_ids=["doc-a"], **extra)


def test_duplicate_retrievers_collapse_and_defaults_are_dense_only():
    assert RetrievalRequest(question="q", document_ids=["d"], retrievers=["bm25", "bm25", "dense"]).retrievers == ["bm25", "dense"]
    assert RetrievalRequest(question="q", document_ids=["d"]).retrievers == ["dense"]
