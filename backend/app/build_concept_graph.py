
"""Build and inspect the Kestrel graph from the backend directory."""

import argparse
import json
import os
from pathlib import Path
from time import monotonic, perf_counter, sleep

from dotenv import load_dotenv
from fastapi import HTTPException
from google import genai
from google.genai import types
from torch import chunk

from app.concept_graph import (
    PROMPT,
    ProviderExtraction,
    build_graph,
    load_graph,
    retrieve_graph,
)
from app.generation import ENV_FILE
from app.evaluation_datasets import read_dataset, resolve_dataset
from app.evaluation_v2 import atomic_write, score_question, summarize
from app.word_chunks import read_word_chunks

from app.redaction import RedactionSession


def evaluate_graph(output):
    graph = load_graph()
    dataset, hashes = read_dataset("kestrel")
    document_ids, questions = resolve_dataset(dataset)
    chunks = {chunk.chunk_id: chunk for chunk in read_word_chunks(document_ids)}
    results = []
    for question in questions:
        started = perf_counter()
        candidates = retrieve_graph(graph, question["question"], document_ids, 10)
        latency = (perf_counter() - started) * 1000
        retrieved = [
            chunks[candidate.chunk_id].model_dump(exclude={"text"}) for candidate in candidates
        ]
        results.append({
            **question, "retrieved": retrieved,
            "graph_candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "scores": score_question(question["evidence"], retrieved),
            "retrieval_error": None, "generation_error": None,
            "retrieval_latency_ms": latency, "llm_calls": 0,
        })
    if load_graph().artifact_id != graph.artifact_id:
        raise ValueError("Graph changed during evaluation. Retry the run.")
    atomic_write(output, {
        "dataset": "kestrel", **hashes, "retrievers": ["graph"],
        "artifact_id": graph.artifact_id, "indexes": graph.indexes,
        "summary": summarize(results),
        "by_type": {
            kind: summarize([item for item in results if item["type"] == kind])
            for kind in sorted({item["type"] for item in results})
        },
        "results": results,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=["kestrel"])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--question", help="Inspect ranked paths in the existing graph.")
    modes.add_argument("--evaluate", type=Path, help="Save a graph-only retrieval run.")
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1-20")
    parser.add_argument(
        "--request-interval", type=float, default=5.0,
        help="Minimum seconds between live provider requests (default: 5).",
    )
    args = parser.parse_args()
    if not 0 <= args.request_interval <= 60:
        parser.error("--request-interval must be between 0 and 60 seconds")
    try:
        if args.evaluate:
            evaluate_graph(args.evaluate)
            return
        if args.question:
            graph = load_graph()
            candidates = retrieve_graph(graph, args.question, list(graph.indexes), args.limit)
            print(json.dumps({
                "artifact_id": graph.artifact_id,
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            }, indent=2))
            return

        load_dotenv(ENV_FILE, override=False)
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        model = os.getenv("GEMINI_MODEL", "").strip()
        if not api_key or not model:
            parser.exit(1, "Set GOOGLE_API_KEY and GEMINI_MODEL in backend/.env.\n")

        config = types.GenerateContentConfig(
            system_instruction=PROMPT,
            response_mime_type="application/json",
            response_json_schema=ProviderExtraction.model_json_schema(),
            temperature=0,
        )

        with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000)) as client:
            next_call = 0.0

            def extract(chunk: str):
                nonlocal next_call
                sleep(max(0.0, next_call - monotonic()))
                next_call = monotonic() + args.request_interval

                redaction = RedactionSession()
                redacted_chunk = redaction.redact(chunk)

                response = client.models.generate_content(
                    model=model,
                    contents=redacted_chunk,
                    config=config,
                )

                usage = response.usage_metadata
                return (
                    response.text or "",
                    usage.prompt_token_count if usage else None,
                    usage.candidates_token_count if usage else None,
                )

            graph = build_graph(model, extract)
        print(f"Graph {graph.artifact_id}: {len(graph.nodes)} entities, {len(graph.edges)} relations")
        print(graph.stats.model_dump_json(indent=2))
    except (ValueError, HTTPException) as error:
        parser.exit(1, f"{getattr(error, 'detail', str(error))}\n")


if __name__ == "__main__":
    main()
