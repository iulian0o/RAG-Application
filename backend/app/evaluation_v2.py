import argparse
import json
import logging
import subprocess
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from filelock import FileLock
from pydantic import Field

from app.answer_contract import INSUFFICIENT_EVIDENCE_MESSAGE
from app.database import DATA_DIR, database
from app.evaluate_retrieval import covers_range, index_snapshot
from app.evaluation_datasets import (
    REPOSITORY_ROOT,
    StrictModel,
    read_dataset,
    resolve_dataset,
)
from app.generation import generate_answer
from app.retrieval import RetrievalRequest, retrieve_chunks


logger = logging.getLogger(__name__)
CUTOFFS = (1, 3, 5, 10)
RESULT_DIRECTORY = REPOSITORY_ROOT / "evaluation" / "results"


class RunRequest(StrictModel):
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    generate_answers: bool = False
    answer_top_k: int = Field(default=5, ge=1, le=10)


def atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")

    try:
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def score_question(evidence: list[dict], chunks: list[dict]) -> dict:
    scores = {}

    for cutoff in CUTOFFS:
        hits = []

        for reference in evidence:
            intervals = [
                (chunk["start"], chunk["end"])
                for chunk in chunks[:cutoff]
                if chunk["document_id"] == reference["document_id"]
            ]
            hits.append(
                covers_range(reference["start"], reference["end"], intervals)
            )

        scores[str(cutoff)] = {
            "evidence_hits": hits,
            "hit": any(hits),
            "complete": bool(hits) and all(hits),
        }

    return scores


def summarize(results: list[dict]) -> dict:
    answerable = [result for result in results if result["answerable"]]
    evidence_count = sum(len(result["evidence"]) for result in answerable)
    metrics = {}

    for cutoff in CUTOFFS:
        scores = [result["scores"][str(cutoff)] for result in answerable]
        metrics[str(cutoff)] = {
            "hit_rate": (
                sum(score["hit"] for score in scores) / len(scores)
                if scores else None
            ),
            "evidence_recall": (
                sum(sum(score["evidence_hits"]) for score in scores)
                / evidence_count
                if evidence_count else None
            ),
            "complete_evidence_rate": (
                sum(score["complete"] for score in scores) / len(scores)
                if scores else None
            ),
        }

    return {
        "questions": len(results),
        "answerable_questions": len(answerable),
        "retrieval_errors": sum(
            result["retrieval_error"] is not None for result in results
        ),
        "generation_errors": sum(
            result["generation_error"] is not None for result in results
        ),
        "metrics": metrics,
    }


def current_snapshot(document_ids: list[str]) -> dict:
    selected = set(document_ids)

    with database() as connection:
        rows = connection.execute(
            "SELECT id, content_hash FROM documents ORDER BY id"
        ).fetchall()

    return {
        "documents": [
            dict(row) for row in rows if row["id"] in selected
        ],
        "indexes": index_snapshot(document_ids),
    }


def safe_error(error: Exception) -> str:
    logger.exception("Evaluation operation failed")
    detail = getattr(error, "detail", None)
    if isinstance(detail, str):
        return detail
    return f"{type(error).__name__}: inspect the backend logs."


def generate_recorded_answer(question: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {
            "status": "insufficient_evidence",
            "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
            "citation_ids": [],
            "model": None,
        }

    answer, model = generate_answer(
        question=question,
        evidence=[
            {"chunk_id": chunk["chunk_id"], "text": chunk["text"]}
            for chunk in chunks
        ],
    )

    value = answer.model_dump()
    if answer.status == "insufficient_evidence":
        value["answer"] = INSUFFICIENT_EVIDENCE_MESSAGE
    value["model"] = model
    return value


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_evaluation(request: RunRequest) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Serializes CLI and API evaluations that share this checkout.
    with FileLock(str(DATA_DIR / "evaluation.lock"), timeout=0):
        return evaluate_locked(request)


def evaluate_locked(request: RunRequest) -> dict:
    dataset, hashes = read_dataset(request.dataset_id)
    document_ids, questions = resolve_dataset(dataset)

    # Validate corpus size and request constraints before starting the run.
    for question in questions:
        RetrievalRequest(
            question=question["question"],
            document_ids=document_ids,
            top_k=10,
        )

    before = current_snapshot(document_ids)
    if len(before["indexes"]) != len(document_ids):
        raise ValueError("Build an index for every corpus document first.")

    run_id = uuid4().hex
    output_path = RESULT_DIRECTORY / f"{run_id}.json"
    results = []

    output = {
        "run_id": run_id,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "dataset_id": request.dataset_id,
        "dataset_name": dataset.name,
        **hashes,
        "git_commit": git_commit(),
        "settings": request.model_dump(),
        "retrieval_cutoffs": list(CUTOFFS),
        "versions": {
            name: version(name)
            for name in ("chromadb", "sentence-transformers", "google-genai")
        },
        "snapshot": before,
        "results": results,
    }
    atomic_write(output_path, output)

    try:
        for question in questions:
            result = {
                **question,
                "retrieved": [],
                "retrieval_error": None,
                "generation_error": None,
                "answer": None,
                "grade": None,
                "grading_notes": None,
                "failure_stage": None,
            }

            try:
                response = retrieve_chunks(
                    RetrievalRequest(
                        question=question["question"],
                        document_ids=document_ids,
                        top_k=10,
                    )
                )
                result["retrieved"] = [
                    chunk.model_dump() for chunk in response.matches
                ]
            except Exception as error:
                result["retrieval_error"] = safe_error(error)

            result["scores"] = score_question(
                result["evidence"], result["retrieved"]
            )

            if request.generate_answers and result["retrieval_error"] is None:
                try:
                    result["answer"] = generate_recorded_answer(
                        question["question"],
                        result["retrieved"][:request.answer_top_k],
                    )
                except Exception as error:
                    result["generation_error"] = safe_error(error)

            results.append(result)
            atomic_write(output_path, output)

        after = current_snapshot(document_ids)
        _, final_hashes = read_dataset(request.dataset_id)

        if before != after or hashes != final_hashes:
            raise RuntimeError(
                "Corpus, indexes, or question sets changed during evaluation."
            )

        output["summary"] = summarize(results)
        output["by_type"] = {
            question_type: summarize(
                [
                    result for result in results
                    if result["type"] == question_type
                ]
            )
            for question_type in sorted({result["type"] for result in results})
        }

        has_errors = any(
            result["retrieval_error"] or result["generation_error"]
            for result in results
        )
        output["status"] = "completed_with_errors" if has_errors else "completed"

    except BaseException:
        output["status"] = "invalid"
        output["error"] = "Run interrupted or inputs changed. Inspect the logs."
        raise
    finally:
        output["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(output_path, output)

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_id")
    parser.add_argument("--generate-answers", action="store_true")
    parser.add_argument("--answer-top-k", type=int, default=5)
    args = parser.parse_args()

    result = run_evaluation(
        RunRequest(
            dataset_id=args.dataset_id,
            generate_answers=args.generate_answers,
            answer_top_k=args.answer_top_k,
        )
    )

    print(json.dumps(result["summary"], indent=2))
    print(f"Run ID: {result['run_id']}")
    print(f"Status: {result['status']}")

    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()