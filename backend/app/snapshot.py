"""One consistent view of the selected documents' active indexes for a single retrieval request.

Every retriever (dense, BM25, graph) of a request reads from the same Snapshot, so they cannot disagree about
which index is active. Callers MUST hold ``index_write_lock`` while they create and use a Snapshot: rebuilding
or deleting a document waits for that lock, so the chunks cannot change underneath a running search.
"""
from collections import Counter
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.database import database
from app.embeddings import MODEL_NAME
from app.vector_store import get_collection
from app.word_chunks import WordChunk, validate_chunk


@dataclass
class Snapshot:
    document_ids: list[str]                 # selected documents, request order, no duplicates
    documents: dict[str, dict]              # document id -> database row (content, hashes, active index_id, ...)
    _chunks: list[WordChunk] | None = field(default=None, repr=False)

    @property
    def active_index_ids(self) -> list[str]:
        return [self.documents[document_id]["index_id"] for document_id in self.document_ids]

    @property
    def document_order(self) -> dict[str, int]:
        return {document_id: position for position, document_id in enumerate(self.document_ids)}

    @property
    def total_chunks(self) -> int:
        return sum(self.documents[document_id]["chunk_count"] for document_id in self.document_ids)

    def read_chunks(self) -> list[WordChunk]:
        """Every active chunk of the selected documents, validated against the source text (read once)."""
        if self._chunks is None:
            stored = get_collection().get(
                where={"index_id": {"$in": self.active_index_ids}},
                include=["documents", "metadatas"],
            )
            ids, texts, metadatas = stored["ids"], stored["documents"], stored["metadatas"]

            if (
                texts is None
                or metadatas is None
                or len(ids) != len(texts)
                or len(ids) != len(metadatas)
                or len(ids) != len(set(ids))
            ):
                raise ValueError("The stored chunk response is inconsistent.")

            chunks = [
                validate_chunk(chunk_id, text, metadata, self.documents)
                for chunk_id, text, metadata in zip(ids, texts, metadatas)
            ]
            counts = Counter(chunk.document_id for chunk in chunks)

            for document_id, document in self.documents.items():
                if counts[document_id] != document["chunk_count"]:
                    raise ValueError("Stored chunks are missing.")

            order = self.document_order
            self._chunks = sorted(chunks, key=lambda c: (order[c.document_id], c.chunk_index))

        return self._chunks


def load_snapshot(document_ids: list[str]) -> Snapshot:
    """Resolve the selected documents to their active indexes (404 / 409 when one is missing or outdated)."""
    selected = list(dict.fromkeys(document_ids))
    placeholders = ",".join("?" for _ in selected)

    with database() as connection:
        rows = connection.execute(
            f"""
            SELECT
                d.id,
                d.filename,
                d.content,
                d.content_hash AS current_hash,
                i.index_id,
                i.content_hash AS indexed_hash,
                i.model_name,
                i.chunk_count
            FROM documents AS d
            LEFT JOIN document_indexes AS i
                ON i.document_id = d.id
            WHERE d.id IN ({placeholders})
            """,
            selected,
        ).fetchall()

    documents = {row["id"]: dict(row) for row in rows}

    for document_id in selected:
        document = documents.get(document_id)

        if document is None:
            raise HTTPException(404, f"Selected document does not exist: {document_id}")

        if document["index_id"] is None:
            raise HTTPException(409, f"Build an index for {document['filename']} first.")

        if (
            document["model_name"] != MODEL_NAME
            or document["current_hash"] != document["indexed_hash"]
        ):
            raise HTTPException(409, f"The index for {document['filename']} is outdated. Rebuild it.")

    if sum(document["chunk_count"] for document in documents.values()) < 1:
        raise HTTPException(409, "The selected indexes contain no chunks. Rebuild them.")

    return Snapshot(document_ids=selected, documents=documents)
