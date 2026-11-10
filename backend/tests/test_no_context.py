from types import SimpleNamespace

from app.evaluate_no_context import ask_without_context


def test_baseline_sends_only_the_question():
    captured = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text="I do not know.")

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )

    answer = ask_without_context(client, "test-model", "What is Kestrel?")

    assert captured["contents"] == "What is Kestrel?"
    assert answer == "I do not know."