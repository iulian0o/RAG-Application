import pytest

from app.evaluation_datasets import Evidence, EvaluationDataset, find_quote


def test_unique_quote_resolves_to_offsets():
    evidence = Evidence(document="guide", quote="beta")
    assert find_quote("alpha beta gamma", evidence) == (6, 10)


def test_repeated_quote_requires_an_offset():
    evidence = Evidence(document="guide", quote="beta")
    with pytest.raises(ValueError, match="ambiguous"):
        find_quote("beta beta", evidence)


def test_explicit_offset_selects_the_requested_occurrence():
    evidence = Evidence(document="guide", quote="beta", start=5)
    assert find_quote("beta beta", evidence) == (5, 9)


def test_wrong_offset_is_rejected():
    evidence = Evidence(document="guide", quote="beta", start=1)
    with pytest.raises(ValueError, match="offset"):
        find_quote("beta beta", evidence)


def test_duplicate_question_ids_are_rejected():
    question = {
        "id": "q1",
        "type": "not in the corpus",
        "question": "What is missing?",
        "answerable": False,
        "expected_answer": "Not in the documents.",
        "evidence": [],
    }

    with pytest.raises(ValueError, match="unique"):
        EvaluationDataset.model_validate(
            {
                "name": "Example",
                "source": "example.source.jsonl",
                "documents": {"guide": {"content_hash": "a" * 64}},
                "questions": [question, question],
            }
        )