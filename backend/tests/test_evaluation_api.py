from fastapi import FastAPI
from fastapi.testclient import TestClient
from filelock import Timeout

from app import evaluation


def make_client():
    app = FastAPI()
    app.include_router(evaluation.router)
    return TestClient(app)


def test_api_uses_retrieval_only_by_default(monkeypatch):
    captured = {}

    def fake_run(request):
        captured.update(request.model_dump())
        return {"run_id": "example", "status": "completed"}

    monkeypatch.setattr(evaluation, "run_evaluation", fake_run)

    response = make_client().post(
        "/api/evaluation/runs",
        json={"dataset_id": "kestrel"},
    )

    assert response.status_code == 201
    assert captured["generate_answers"] is False


def test_api_rejects_invalid_answer_cutoff():
    response = make_client().post(
        "/api/evaluation/runs",
        json={"dataset_id": "kestrel", "answer_top_k": 11},
    )

    assert response.status_code == 422


def test_api_reports_an_evaluation_already_running(monkeypatch):
    def busy(request):
        raise Timeout("evaluation.lock")

    monkeypatch.setattr(evaluation, "run_evaluation", busy)

    response = make_client().post(
        "/api/evaluation/runs",
        json={"dataset_id": "kestrel"},
    )

    assert response.status_code == 409


def test_api_rejects_path_like_run_ids():
    response = make_client().get("/api/evaluation/runs/not-a-uuid")
    assert response.status_code == 422