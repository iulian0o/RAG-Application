import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from filelock import Timeout
from pydantic import BaseModel

from app.evaluation_datasets import DATASET_DIRECTORY, read_dataset
from app.evaluation_v2 import RESULT_DIRECTORY, RunRequest, run_evaluation


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


class QuestionSummary(BaseModel):
    id: str
    type: str
    question: str


class DatasetSummary(BaseModel):
    id: str
    name: str
    questions: list[QuestionSummary]


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets():
    datasets = []

    for path in sorted(DATASET_DIRECTORY.glob("*.json")):
        try:
            dataset, _ = read_dataset(path.stem)
        except (OSError, ValueError):
            logger.exception("Invalid evaluation dataset %s", path.name)
            raise HTTPException(
                503,
                f"Dataset '{path.stem}' is invalid. Check the backend logs.",
            ) from None

        datasets.append(
            DatasetSummary(
                id=path.stem,
                name=dataset.name,
                questions=[
                    QuestionSummary(
                        id=question.id,
                        type=question.type,
                        question=question.question,
                    )
                    for question in dataset.questions
                ],
            )
        )

    return datasets


@router.post("/runs", status_code=201)
def create_run(request: RunRequest):
    try:
        return run_evaluation(request)
    except Timeout:
        raise HTTPException(
            409, "Another evaluation is running. Retry after it completes."
        ) from None
    except FileNotFoundError:
        raise HTTPException(
            404, "The dataset or its source JSONL file was not found."
        ) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error
    except Exception:
        logger.exception("Evaluation failed")
        raise HTTPException(
            500, "Evaluation failed. Check the backend logs."
        ) from None


@router.get("/runs/{run_id}")
def get_run(run_id: UUID):
    path = RESULT_DIRECTORY / f"{run_id.hex}.json"

    if not path.is_file():
        raise HTTPException(404, "Evaluation run not found.")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(500, "The saved result could not be read.") from None