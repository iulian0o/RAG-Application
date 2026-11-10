import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.evaluation_datasets import read_dataset
from app.evaluation_v2 import RESULT_DIRECTORY, atomic_write, git_commit
from app.generation import ENV_FILE


BASELINE_INSTRUCTION = (
    "Answer the question using your own knowledge. "
    "If you do not know, say that you do not know."
)


def ask_without_context(client, model: str, question: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=BASELINE_INSTRUCTION,
            max_output_tokens=2048,
        ),
    )

    answer = response.text
    if not answer or not answer.strip():
        raise ValueError("The model returned an empty answer.")

    return answer.strip()


def run_baseline(dataset_id: str) -> dict:
    dataset, hashes = read_dataset(dataset_id)
    load_dotenv(ENV_FILE, override=False)

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip()

    if not api_key or not model:
        raise ValueError("Configure GOOGLE_API_KEY and GEMINI_MODEL first.")

    run_id = uuid4().hex
    output_path = RESULT_DIRECTORY / f"no-context-{run_id}.json"
    output = {
        "run_id": run_id,
        "kind": "no_context",
        "status": "running",
        "dataset_id": dataset_id,
        **hashes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "model": model,
        "system_instruction": BASELINE_INSTRUCTION,
        "results": [],
    }
    atomic_write(output_path, output)

    try:
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60000),
        ) as client:
            for question in dataset.questions:
                result = {
                    "id": question.id,
                    "question": question.question,
                    "expected_answer": question.expected_answer,
                    "answer": None,
                    "error": None,
                    "correct_without_context": None,
                    "review_notes": None,
                }

                try:
                    result["answer"] = ask_without_context(
                        client, model, question.question
                    )
                except Exception as error:
                    result["error"] = type(error).__name__

                output["results"].append(result)
                atomic_write(output_path, output)

        _, final_hashes = read_dataset(dataset_id)
        if hashes != final_hashes:
            raise RuntimeError("The question set changed during the baseline.")

        has_errors = any(result["error"] for result in output["results"])
        output["status"] = (
            "completed_with_errors" if has_errors else "completed"
        )
    except BaseException:
        output["status"] = "invalid"
        raise
    finally:
        output["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(output_path, output)

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_id")
    args = parser.parse_args()

    result = run_baseline(args.dataset_id)
    print(json.dumps(
        {"run_id": result["run_id"], "status": result["status"]},
        indent=2,
    ))

    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()