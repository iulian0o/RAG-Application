import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from app.database import database
from app.retrieval import RetrievalRequest, retrieve_chunks


def covers_range(start: int, end: int, intervals: list[tuple[int, int]]) -> bool:
    cursor = start

    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            return False

        cursor = max(cursor, right)

        if cursor >= end:
            return True

    return False


def index_snapshot(document_ids: list[str]) -> list[dict]:
    with database() as connection:
        rows = connection.execute(
            "SELECT * FROM document_indexes ORDER BY document_id"
        ).fetchall()

    selected = set(document_ids)
    return [dict(row) for row in rows if row["document_id"] in selected]


def evaluate(dataset_path: Path, output_path: Path, top_k: int) -> None:
    raw_dataset = dataset_path.read_bytes()
    dataset = json.loads(raw_dataset)

    with database() as connection:
        rows = connection.execute(
            "SELECT id, filename, content_hash, content FROM documents"
        ).fetchall()

    by_hash = {row["content_hash"]: dict(row) for row in rows}
    documents = {}

    for key, specification in dataset["documents"].items():
        content_hash = specification["content_hash"]

        if content_hash not in by_hash:
            raise ValueError(
                f"Document '{key}' is missing or its content has changed."
            )

        documents[key] = by_hash[content_hash]

    questions = dataset["questions"]

    if not questions:
        raise ValueError("The dataset must contain questions.")

    seen_ids = set()

    for question in questions:
        if question["id"] in seen_ids:
            raise ValueError(f"Duplicate question ID: {question['id']}")

        seen_ids.add(question["id"])

        if not question["expected_answer"].strip():
            raise ValueError("Each question needs an expected answer.")

        if not isinstance(question["answerable"], bool):
            raise ValueError("answerable must be true or false.")

        selected_keys = question["document_keys"]

        if not selected_keys or any(key not in documents for key in selected_keys):
            raise ValueError(f"Invalid document selection: {question['id']}")

        if len(selected_keys) != len(set(selected_keys)):
            raise ValueError(f"Duplicate selected document: {question['id']}")

        if question["answerable"] != bool(question["evidence"]):
            raise ValueError(
                f"Answerable questions need evidence; unanswerable ones must "
                f"have none: {question['id']}"
            )

        seen_evidence = set()

        for evidence in question["evidence"]:
            key = evidence["document_key"]
            start = evidence["start"]
            end = evidence["end"]

            if key not in selected_keys:
                raise ValueError("Evidence must belong to a selected document.")

            if (
                type(start) is not int
                or type(end) is not int
                or not 0 <= start < end <= len(documents[key]["content"])
            ):
                raise ValueError(f"Invalid evidence offsets: {question['id']}")

            evidence_key = (key, start, end)

            if evidence_key in seen_evidence:
                raise ValueError(f"Duplicate evidence range: {question['id']}")

            seen_evidence.add(evidence_key)

        # Validate requests before starting any searches.
        RetrievalRequest(
            question=question["question"],
            document_ids=[documents[key]["id"] for key in selected_keys],
            top_k=top_k,
        )

    document_ids = [document["id"] for document in documents.values()]
    before = index_snapshot(document_ids)

    if len(before) != len(set(document_ids)):
        raise ValueError("Build an index for every benchmark document first.")

    results = []

    for question in questions:
        request = RetrievalRequest(
            question=question["question"],
            document_ids=[
                documents[key]["id"]
                for key in question["document_keys"]
            ],
            top_k=top_k,
        )

        error = None
        matches = []

        try:
            matches = retrieve_chunks(request).matches
        except Exception as exception:
            error = str(getattr(exception, "detail", exception))

        evidence_hits = []

        for evidence in question["evidence"]:
            document_id = documents[evidence["document_key"]]["id"]

            intervals = [
                (match.start, match.end)
                for match in matches
                if match.document_id == document_id
            ]

            evidence_hits.append(
                covers_range(evidence["start"], evidence["end"], intervals)
            )

        results.append(
            {
                "id": question["id"],
                "question": question["question"],
                "answerable": question["answerable"],
                "expected_answer": question["expected_answer"],
                "error": error,
                "evidence_hits": evidence_hits,
                "retrieved": [
                    match.model_dump(exclude={"text"})
                    for match in matches
                ],
            }
        )

    if before != index_snapshot(document_ids):
        raise RuntimeError(
            "Indexes changed during evaluation. Run again without rebuilding."
        )

    answerable = [result for result in results if result["answerable"]]
    evidence_total = sum(len(result["evidence_hits"]) for result in answerable)
    evidence_found = sum(sum(result["evidence_hits"]) for result in answerable)

    summary = {
        "questions": len(results),
        "answerable_questions": len(answerable),
        "unanswerable_questions": len(results) - len(answerable),
        "errors": sum(result["error"] is not None for result in results),
        "hit_at_k": (
            sum(any(result["evidence_hits"]) for result in answerable)
            / len(answerable)
            if answerable else None
        ),
        "evidence_recall_at_k": (
            evidence_found / evidence_total if evidence_total else None
        ),
        "complete_evidence_rate": (
            sum(all(result["evidence_hits"]) for result in answerable)
            / len(answerable)
            if answerable else None
        ),
    }

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None

    output = {
        "dataset": dataset["name"],
        "dataset_sha256": hashlib.sha256(raw_dataset).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "top_k": top_k,
        "versions": {
            package: version(package)
            for package in ["chromadb", "sentence-transformers"]
        },
        "indexes": before,
        "summary": summary,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    print(f"Saved results to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    evaluate(args.dataset, args.output, args.top_k)