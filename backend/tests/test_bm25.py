from app import bm25
from app.bm25 import Bm25Index, bm25_tokens
from app.word_chunks import WordChunk


def chunk(text, number, document="doc-1", index="idx-1"):
    return WordChunk(
        chunk_id=f"{index}:{number}", document_id=document, index_id=index, filename="f.txt",
        content_hash="h", chunk_index=number, start=0, end=len(text), text=text,
    )


ORDER = {"doc-1": 0, "doc-2": 1}


def test_identifiers_stay_whole_and_are_also_split():
    assert bm25_tokens("Error E47 in SVC-ORBIT") == ["error", "e47", "in", "svc-orbit", "svc", "orbit"]
    assert bm25_tokens("snake_case") == ["snake_case", "snake", "case"]
    assert bm25_tokens("Hello, world!") == ["hello", "world"]


def test_exact_identifier_beats_a_paraphrase():
    chunks = [
        chunk("The grinder makes noise when beans run out. Refill the hopper.", 0),
        chunk("E47 - Grinder blocked by a foreign object. Unplug the machine.", 1),
        chunk("Descale the machine every three months to avoid limescale.", 2),
    ]
    hits = Bm25Index(chunks).search("What does error E47 mean?", 5, ORDER)

    assert hits[0].chunk.chunk_index == 1
    assert "e47" in hits[0].matched_terms
    assert all(hit.score > 0 for hit in hits)


def test_hyphenated_identifier_matches_parts_but_exact_scores_higher():
    chunks = [
        chunk("The orbit of the moon is elliptical.", 0),
        chunk("Aurora Reports depends on SVC-ORBIT for region data.", 1),
        chunk("Unrelated text about bread and flour.", 2),
    ]
    index = Bm25Index(chunks)

    exact = index.search("Which region does SVC-ORBIT serve?", 5, ORDER)
    spaced = index.search("svc orbit", 5, ORDER)

    assert exact[0].chunk.chunk_index == 1
    assert spaced[0].chunk.chunk_index == 1
    assert 2 not in [hit.chunk.chunk_index for hit in exact]


def test_no_matching_word_returns_nothing():
    index = Bm25Index([chunk("alpha beta gamma", 0)])
    assert index.search("zzzz qqqq", 5, ORDER) == []
    assert Bm25Index([]).search("anything", 5, ORDER) == []


def test_limit_and_tie_order_follow_document_then_position():
    chunks = [chunk("same words here", 1, "doc-2", "idx-2"), chunk("same words here", 0, "doc-1", "idx-1"),
              chunk("same words here", 1, "doc-1", "idx-1")]
    hits = Bm25Index(chunks).search("same words", 2, ORDER)

    assert [(h.chunk.document_id, h.chunk.chunk_index) for h in hits] == [("doc-1", 0), ("doc-1", 1)]


def test_repeated_terms_saturate_and_long_chunks_are_penalised():
    short = chunk("raven", 0)
    long = chunk("raven " + "filler " * 50, 1)
    hits = Bm25Index([short, long]).search("raven", 5, ORDER)

    assert [h.chunk.chunk_index for h in hits] == [0, 1]


def test_cache_is_keyed_by_active_index_ids_and_reads_chunks_once():
    bm25.clear_cache()
    calls = []

    def reader():
        calls.append(1)
        return [chunk("alpha", 0)]

    first = bm25.get_index(["idx-b", "idx-a"], reader)
    second = bm25.get_index(["idx-a", "idx-b"], reader)       # same set, other order: cache hit

    assert first is second and len(calls) == 1

    rebuilt = bm25.get_index(["idx-a", "idx-c"], lambda: [chunk("beta", 0, index="idx-c")])
    assert rebuilt is not first                                  # a rebuild gives a new index ID: never the old entry
    assert rebuilt.search("alpha", 5, ORDER) == []


def test_cache_is_bounded(monkeypatch):
    bm25.clear_cache()
    monkeypatch.setattr(bm25, "CACHE_SIZE", 2)

    for name in ("a", "b", "c"):
        bm25.get_index([name], lambda: [chunk("x", 0)])

    assert len(bm25._cache) == 2
    assert ("a",) not in bm25._cache
    bm25.clear_cache()
