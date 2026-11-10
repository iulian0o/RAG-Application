from app import evaluation_v2 as evaluation


def test_cutoffs_use_ranked_prefixes():
    evidence = [{"document_id": "doc", "start": 10, "end": 20}]
    chunks = [
        {"document_id": "other", "start": 0, "end": 30},
        {"document_id": "doc", "start": 0, "end": 30},
    ]

    scores = evaluation.score_question(evidence, chunks)

    assert scores["1"]["hit"] is False
    assert scores["3"]["hit"] is True
    assert scores["5"]["complete"] is True
    assert scores["10"]["complete"] is True


def test_unanswerable_questions_are_excluded_from_denominators():
    evidence = [{"document_id": "doc", "start": 0, "end": 4}]
    chunks = [{"document_id": "doc", "start": 0, "end": 4}]

    answered = {
        "answerable": True,
        "evidence": evidence,
        "scores": evaluation.score_question(evidence, chunks),
        "retrieval_error": None,
        "generation_error": None,
    }
    unanswerable = {
        "answerable": False,
        "evidence": [],
        "scores": evaluation.score_question([], []),
        "retrieval_error": None,
        "generation_error": None,
    }

    summary = evaluation.summarize([answered, unanswerable])

    assert summary["questions"] == 2
    assert summary["answerable_questions"] == 1
    assert summary["metrics"]["1"]["hit_rate"] == 1.0


def test_retrieval_failure_counts_as_a_miss():
    evidence = [{"document_id": "doc", "start": 0, "end": 4}]
    result = {
        "answerable": True,
        "evidence": evidence,
        "scores": evaluation.score_question(evidence, []),
        "retrieval_error": "Unavailable",
        "generation_error": None,
    }

    summary = evaluation.summarize([result])

    assert summary["retrieval_errors"] == 1
    assert summary["metrics"]["1"]["hit_rate"] == 0.0


def test_empty_evidence_returns_abstention_without_calling_model(monkeypatch):
    def unexpected_call(**kwargs):
        raise AssertionError("The model should not be called.")

    monkeypatch.setattr(evaluation, "generate_answer", unexpected_call)

    result = evaluation.generate_recorded_answer("Unknown?", [])

    assert result["status"] == "insufficient_evidence"
    assert result["citation_ids"] == []


def test_generation_receives_recorded_chunk_text(monkeypatch):
    from app.answer_contract import DraftAnswer

    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return (
            DraftAnswer(
                status="answered",
                answer="At dawn.",
                citation_ids=["chunk-1"],
            ),
            "test-model",
        )

    monkeypatch.setattr(evaluation, "generate_answer", fake_generate)

    result = evaluation.generate_recorded_answer(
        "When?",
        [{"chunk_id": "chunk-1", "text": "The raven arrived at dawn."}],
    )

    assert captured["evidence"] == [
        {"chunk_id": "chunk-1", "text": "The raven arrived at dawn."}
    ]
    assert result["model"] == "test-model"