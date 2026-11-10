import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database import database


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = REPOSITORY_ROOT / "evaluation" / "datasets"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentReference(StrictModel):
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class Evidence(StrictModel):
    document: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    start: int | None = Field(default=None, ge=0)


class EvaluationQuestion(StrictModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    answerable: bool
    expected_answer: str = Field(min_length=1)
    evidence: list[Evidence]

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.answerable != bool(self.evidence):
            raise ValueError(
                "Answerable questions need evidence. "
                "Unanswerable questions must have none."
            )
        return self


class EvaluationDataset(StrictModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    documents: dict[str, DocumentReference] = Field(min_length=1)
    questions: list[EvaluationQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_questions(self):
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question IDs must be unique.")

        hashes = [document.content_hash for document in self.documents.values()]
        if len(hashes) != len(set(hashes)):
            raise ValueError("Each corpus document must appear only once.")

        for question in self.questions:
            for evidence in question.evidence:
                if evidence.document not in self.documents:
                    raise ValueError(
                        f"Unknown evidence document in question {question.id}."
                    )
        return self


def read_dataset(dataset_id: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", dataset_id):
        raise ValueError("Invalid dataset ID.")

    path = DATASET_DIRECTORY / f"{dataset_id}.json"
    raw = path.read_bytes()
    dataset = EvaluationDataset.model_validate_json(raw)

    source_path = (DATASET_DIRECTORY / dataset.source).resolve()
    if source_path.parent != DATASET_DIRECTORY.resolve():
        raise ValueError("The source JSONL must be inside the datasets directory.")
    if source_path.suffix != ".jsonl":
        raise ValueError("The source question set must be JSONL.")

    source_raw = source_path.read_bytes()
    source_records = [
        json.loads(line)
        for line in source_raw.decode("utf-8-sig").splitlines()
        if line.strip()
    ]

    if not all(isinstance(record, dict) for record in source_records):
        raise ValueError("Each source JSONL line must contain an object.")
    if len(source_records) != len(dataset.questions):
        raise ValueError("Source and adapter question counts differ.")

    hashes = {
        "adapter_sha256": hashlib.sha256(raw).hexdigest(),
        "source_sha256": hashlib.sha256(source_raw).hexdigest(),
    }
    return dataset, hashes


def find_quote(content: str, evidence: Evidence) -> tuple[int, int]:
    if evidence.start is not None:
        start = evidence.start
        end = start + len(evidence.quote)
        if content[start:end] != evidence.quote:
            raise ValueError("The quote does not match the supplied offset.")
        return start, end

    start = content.find(evidence.quote)
    if start < 0:
        raise ValueError("The reference quote is absent from the document.")

    if content.find(evidence.quote, start + 1) >= 0:
        raise ValueError("The quote is ambiguous. Supply its start offset.")

    return start, start + len(evidence.quote)


def resolve_dataset(dataset: EvaluationDataset):
    with database() as connection:
        rows = connection.execute(
            "SELECT id, content_hash, content FROM documents"
        ).fetchall()

    documents_by_hash = {row["content_hash"]: dict(row) for row in rows}
    documents = {}

    for key, reference in dataset.documents.items():
        document = documents_by_hash.get(reference.content_hash)
        if document is None:
            raise ValueError(f"Upload the expected corpus document '{key}' first.")
        documents[key] = document

    questions = []

    for question in dataset.questions:
        resolved = question.model_dump()
        resolved["evidence"] = []
        seen = set()

        for evidence in question.evidence:
            document = documents[evidence.document]
            start, end = find_quote(document["content"], evidence)
            identity = (document["id"], start, end)

            if identity in seen:
                raise ValueError(f"Duplicate evidence in question {question.id}.")
            seen.add(identity)

            resolved["evidence"].append(
                {
                    "document_id": document["id"],
                    "quote": evidence.quote,
                    "start": start,
                    "end": end,
                }
            )

        questions.append(resolved)

    return [document["id"] for document in documents.values()], questions