import logging
from collections import Counter

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from app.database import database
from app.embeddings import MODEL_NAME
from app.indexing import index_write_lock
from app.vector_store import get_collection


logger = logging.getLogger(__name__)


class WordChunk(BaseModel):
    model_config = ConfigDict(strict=True)

    chunk_id: str
    document_id: str
    index_id: str
    filename: str
    content_hash: str
    chunk_index: int
    start: int
    end: int
    text: str


def validate_chunk(
    chunk_id: str,
    text: str,
    metadata: dict,
    documents: dict,
) -> WordChunk:
    document = documents.get(metadata.get("document_id"))

    if document is None:
        raise ValueError("The index returned an unselected document.")

    if (
        metadata.get("index_id") != document["index_id"]
        or metadata.get("content_hash") != document["current_hash"]
    ):
        raise ValueError("The index returned an outdated chunk.")

    position = metadata.get("chunk_index")
    start = metadata.get("start")
    end = metadata.get("end")

    if (
        type(position) is not int
        or not 0 <= position < document["chunk_count"]
        or chunk_id != f"{document['index_id']}:{position}"
    ):
        raise ValueError("The stored chunk ID is inconsistent.")

    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(document["content"])
        or text != document["content"][start:end]
    ):
        raise ValueError("The stored chunk does not match its source.")

    return WordChunk(
        chunk_id=chunk_id,
        document_id=document["id"],
        index_id=document["index_id"],
        filename=document["filename"],
        content_hash=document["current_hash"],
        chunk_index=position,
        start=start,
        end=end,
        text=text,
    )


def read_word_chunks(document_ids: list[str]) -> list[WordChunk]:
    selected_ids = list(dict.fromkeys(document_ids))

    if not selected_ids:
        raise HTTPException(422, "Select at least one document.")

    if not index_write_lock.acquire(blocking=False):
        raise HTTPException(
            409,
            "An index operation is running. Retry shortly.",
        )

    try:
        placeholders = ",".join("?" for _ in selected_ids)

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
                selected_ids,
            ).fetchall()

        documents = {row["id"]: dict(row) for row in rows}

        for document_id in selected_ids:
            document = documents.get(document_id)

            if document is None:
                raise HTTPException(404, "A selected document no longer exists.")

            if document["index_id"] is None:
                raise HTTPException(
                    409,
                    f"Build an index for {document['filename']} first.",
                )

            if (
                document["current_hash"] != document["indexed_hash"]
                or document["model_name"] != MODEL_NAME
            ):
                raise HTTPException(
                    409,
                    f"Rebuild the outdated index for {document['filename']}.",
                )

            if document["chunk_count"] < 1:
                raise HTTPException(
                    409,
                    f"The index for {document['filename']} contains no chunks.",
                )

        active_index_ids = [
            documents[document_id]["index_id"]
            for document_id in selected_ids
        ]

        stored = get_collection().get(
            where={"index_id": {"$in": active_index_ids}},
            include=["documents", "metadatas"],
        )

        ids = stored["ids"]
        texts = stored["documents"]
        metadatas = stored["metadatas"]

        if (
            texts is None
            or metadatas is None
            or len(ids) != len(texts)
            or len(ids) != len(metadatas)
            or len(ids) != len(set(ids))
        ):
            raise ValueError("The stored chunk response is inconsistent.")

        chunks = [
            validate_chunk(chunk_id, text, metadata, documents)
            for chunk_id, text, metadata in zip(ids, texts, metadatas)
        ]

        counts = Counter(chunk.document_id for chunk in chunks)

        for document_id, document in documents.items():
            if counts[document_id] != document["chunk_count"]:
                raise ValueError("Stored chunks are missing.")

        return sorted(
            chunks,
            key=lambda chunk: (chunk.document_id, chunk.chunk_index),
        )

    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Could not read chunks for word analytics")
        raise HTTPException(
            503,
            "Could not read consistent chunks. Check or rebuild the indexes.",
        ) from error
    finally:
        index_write_lock.release()