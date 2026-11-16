"""BM25 keyword retrieval over the active chunks of the selected documents (in memory, no extra service).

Tokenization
    Reuses ``word_tokens.tokenize`` (NFKC, case-folded). A token keeps its hyphens and underscores, so the
    identifiers ``E47`` and ``SVC-ORBIT`` stay whole. A compound token is also indexed as its parts, so
    ``SVC-ORBIT`` produces ``svc-orbit``, ``svc`` and ``orbit``: a question written "SVC ORBIT" or "orbit"
    still finds it, while the exact identifier matches all three terms and scores higher.
    The same function tokenizes documents and questions.
Scoring
    Okapi BM25 with k1 = 1.5 and b = 0.75 (the values of bm25/ask_bm25_rag_google.py) and the non-negative
    IDF ln(1 + (N - df + 0.5) / (df + 0.5)). Only chunks sharing at least one term with the question are
    candidates: a question with no matching word returns nothing (dense search always returns something).
Cache
    The index is built from the validated active chunks and kept in memory under the key "sorted active index
    IDs". Rebuilding a document creates a new index ID, so the old entry is never used again; changing or
    deleting a document is rejected by the snapshot check before the cache is consulted. At most
    ``CACHE_SIZE`` indexes are kept (least recently used leave first). ``clear_cache()`` empties it.
"""
import math
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass
from threading import Lock

from app.word_chunks import WordChunk
from app.word_tokens import tokenize


K1 = 1.5
B = 0.75
CACHE_SIZE = 8

_PARTS = re.compile(r"[^-_]+")


def bm25_tokens(text: str) -> list[str]:
    tokens: list[str] = []

    for token in tokenize(text):
        tokens.append(token)

        if "-" in token or "_" in token:
            parts = _PARTS.findall(token)

            if len(parts) > 1:
                tokens.extend(parts)

    return tokens


@dataclass(frozen=True)
class Bm25Hit:
    chunk: WordChunk
    score: float
    matched_terms: tuple[str, ...]


class Bm25Index:
    def __init__(self, chunks: list[WordChunk]):
        self.chunks = chunks
        self.lengths: list[int] = []
        self.postings: dict[str, list[tuple[int, int]]] = {}

        for position, chunk in enumerate(chunks):
            counts = Counter(bm25_tokens(chunk.text))
            self.lengths.append(sum(counts.values()))

            for term, frequency in counts.items():
                self.postings.setdefault(term, []).append((position, frequency))

        total = sum(self.lengths)
        self.average_length = total / len(chunks) if chunks and total else 1.0

    def search(
        self,
        question: str,
        limit: int,
        document_order: dict[str, int],
    ) -> list[Bm25Hit]:
        count = len(self.chunks)
        scores: dict[int, float] = {}
        matched: dict[int, list[str]] = {}

        for term in dict.fromkeys(bm25_tokens(question)):
            postings = self.postings.get(term)

            if not postings:
                continue

            document_frequency = len(postings)
            idf = math.log(1 + (count - document_frequency + 0.5) / (document_frequency + 0.5))

            for position, frequency in postings:
                normaliser = K1 * (1 - B + B * self.lengths[position] / self.average_length)
                scores[position] = scores.get(position, 0.0) + idf * frequency * (K1 + 1) / (frequency + normaliser)
                matched.setdefault(position, []).append(term)

        # Highest score first; ties by the order the documents were selected, then by position in the document.
        ranked = sorted(
            scores,
            key=lambda p: (
                -round(scores[p], 12),
                document_order.get(self.chunks[p].document_id, 0),
                self.chunks[p].chunk_index,
            ),
        )

        return [
            Bm25Hit(self.chunks[p], scores[p], tuple(matched[p]))
            for p in ranked[:limit]
            if scores[p] > 0
        ]


_cache: "OrderedDict[tuple[str, ...], Bm25Index]" = OrderedDict()
_cache_lock = Lock()


def get_index(active_index_ids: list[str], read_chunks) -> Bm25Index:
    """Cached index for these active indexes; ``read_chunks`` is only called on a cache miss."""
    key = tuple(sorted(active_index_ids))

    with _cache_lock:
        index = _cache.get(key)

        if index is not None:
            _cache.move_to_end(key)
            return index

    index = Bm25Index(read_chunks())

    with _cache_lock:
        _cache[key] = index
        _cache.move_to_end(key)

        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)

    return index


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
