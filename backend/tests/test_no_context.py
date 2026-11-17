from types import SimpleNamespace

import pytest

from app.evaluate_no_context import ask_without_context


@pytest.mark.parametrize(
    ("question", "provider_text"),
    [
        ("What is Kestrel?", "What is Kestrel?"),
        ("Who uses synthetic@example.test?", "Who uses [EMAIL_1]?"),
    ],
)
def test_baseline_sends_only_the_question(question, provider_text):
    captured = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text="I do not know.")

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )

    answer = ask_without_context(client, "test-model", question)

    assert captured["contents"] == provider_text
    assert answer == "I do not know."
