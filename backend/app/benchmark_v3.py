"""V3 retrieval benchmark: run one dataset under several retrieval configurations and compare them.

    python -m app.benchmark_v3 kestrel --config dense --config dense+bm25 --config dense+bm25@bm25=0.5
    python -m app.benchmark_v3 custom  --config dense --config dense+bm25 --depth 50

A configuration is  retriever[+retriever...][@name=weight,...]   (retrievers: dense, bm25, graph).
Without "@" the fusion is plain RRF; with it, weighted RRF. Every configuration sees the same questions, corpus
and indexes. Retrieval only (no model call, no API key). It reuses the V2 scoring (Recall and HitRate at 1, 3, 5,
10, overall and by question type) and writes, under evaluation/results/:

    v3-<run_id>.json        one file per configuration (settings, hashes, index settings, git commit, per-question
                            results with fused and per-retriever ranks and retrieval latency)
    v3-compare-<time>.csv   one row per configuration, group and cutoff, in the format of comparison.csv plus a
                            "config" column

Do not change documents, indexes or the question set while it runs: the run is then marked invalid.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from importlib.metadata import version
from uuid import uuid4

from filelock import FileLock

from app.database import DATA_DIR
from app.evaluation_datasets import read_dataset, resolve_dataset
from app.evaluation_v2 import (
    CUTOFFS,
    RESULT_DIRECTORY,
    atomic_write,
    current_snapshot,
    git_commit,
    safe_error,
    score_question,
    summarize,
)
from app.retrieval import RetrievalRequest, retrieve_chunks

VALID_RETRIEVERS = ("dense", "bm25", "graph")


def parse_config(text: str) -> dict:
    """'dense+bm25@bm25=0.5' -> {'name': ..., 'retrievers': ['dense', 'bm25'], 'weights': {'bm25': 0.5}}"""
    names, _, weight_text = text.strip().partition("@")
    retrievers = [name.strip() for name in names.split("+") if name.strip()]

    if not retrievers or any(name not in VALID_RETRIEVERS for name in retrievers) or len(set(retrievers)) != len(retrievers):
        raise ValueError(f"Invalid configuration '{text}': use retrievers from {', '.join(VALID_RETRIEVERS)} joined by '+'.")

    weights = None

    if weight_text:
        weights = {}
        for part in weight_text.split(","):
            name, _, value = part.partition("=")

            try:
                weights[name.strip()] = float(value)
            except ValueError:
                raise ValueError(f"Invalid weight in '{text}': expected name=number.") from None

        if not set(weights) <= set(retrievers):
            raise ValueError(f"Weights in '{text}' must belong to enabled retrievers.")

    return {"name": text.strip(), "retrievers": retrievers, "weights": weights}


def first_hit_rank(evidence: list[dict], chunks: list[dict]) -> int | None:
    """Fused rank of the first retrieved chunk that overlaps any evidence span (None: no chunk does)."""
    for rank, chunk in enumerate(chunks, start=1):
        for reference in evidence:
            if (
                chunk["document_id"] == reference["document_id"]
                and chunk["start"] < reference["end"]
                and reference["start"] < chunk["end"]
            ):
                return rank

    return None


def run_configuration(dataset_id: str, config: dict, depth: int | None, rrf_k: int) -> dict:
    dataset, hashes = read_dataset(dataset_id)
    document_ids, questions = resolve_dataset(dataset)
    before = current_snapshot(document_ids)

    if len(before["indexes"]) != len(document_ids):
        raise ValueError("Build an index for every corpus document first.")

    run_id = uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    results = []

    for question in questions:
        result = {
            **question,
            "retrieved": [],
            "retrieval_error": None,
            "generation_error": None,
            "retrieval_latency_ms": None,
            "timings_ms": None,
        }

        try:
            response = retrieve_chunks(
                RetrievalRequest(
                    question=question["question"],
                    document_ids=document_ids,
                    top_k=max(CUTOFFS),
                    retrievers=config["retrievers"],
                    candidate_depth=depth,
                    rrf_k=rrf_k,
                    weights=config["weights"],
                )
            )
            result["retrieved"] = [chunk.model_dump() for chunk in response.matches]
            result["timings_ms"] = response.timings_ms
            result["retrieval_latency_ms"] = response.timings_ms.get("total")
        except Exception as error:
            result["retrieval_error"] = safe_error(error)

        result["scores"] = score_question(question["evidence"], result["retrieved"])
        result["first_hit_rank"] = first_hit_rank(question["evidence"], result["retrieved"])
        results.append(result)

    after = current_snapshot(document_ids)
    _, final_hashes = read_dataset(dataset_id)

    output = {
        "run_id": run_id,
        "kind": "v3-benchmark",
        "status": "invalid",
        "created_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        **hashes,
        "git_commit": git_commit(),
        "retrieval_config": {
            "name": config["name"],
            "retrievers": config["retrievers"],
            "fusion": "weighted_rrf" if config["weights"] else "rrf",
            "weights": config["weights"],
            "rrf_k": rrf_k,
            "candidate_depth": depth,
            "final_top_k": max(CUTOFFS),
        },
        "retrieval_cutoffs": list(CUTOFFS),
        "versions": {name: version(name) for name in ("chromadb", "sentence-transformers")},
        "snapshot": before,
        "results": results,
    }

    if before != after or hashes != final_hashes:
        output["error"] = "Corpus, indexes, or question sets changed during the run."
        atomic_write(RESULT_DIRECTORY / f"v3-{run_id}.json", output)
        raise RuntimeError(output["error"])

    output["summary"] = summarize(results)
    output["by_type"] = {
        question_type: summarize([r for r in results if r["type"] == question_type])
        for question_type in sorted({r["type"] for r in results})
    }
    latencies = [r["retrieval_latency_ms"] for r in results if r["retrieval_latency_ms"] is not None]
    output["latency_ms"] = {
        "mean": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "max": max(latencies) if latencies else None,
    }
    output["status"] = "completed_with_errors" if any(r["retrieval_error"] for r in results) else "completed"
    atomic_write(RESULT_DIRECTORY / f"v3-{run_id}.json", output)
    return output


def comparison_rows(outputs: list[dict]) -> list[dict]:
    rows = []

    for output in outputs:
        settings = json.dumps(
            [{k: row[k] for k in ("document_id", "chunk_size", "overlap", "model_name")} for row in output["snapshot"]["indexes"]],
            separators=(",", ":"),
        )
        groups = {"overall": output["summary"], **output["by_type"]}

        for group, summary in groups.items():
            for cutoff in CUTOFFS:
                metrics = summary["metrics"][str(cutoff)]
                rows.append(
                    {
                        "config": output["retrieval_config"]["name"],
                        "dataset": output["dataset_id"],
                        "run_id": output["run_id"],
                        "adapter_sha256": output["adapter_sha256"],
                        "source_sha256": output["source_sha256"],
                        "index_settings": settings,
                        "candidate_depth": output["retrieval_config"]["candidate_depth"],
                        "rrf_k": output["retrieval_config"]["rrf_k"],
                        "git_commit": output["git_commit"],
                        "group": group,
                        "n": summary["answerable_questions"],
                        "k": cutoff,
                        "hit_rate": metrics["hit_rate"],
                        "evidence_recall": metrics["evidence_recall"],
                        "complete_evidence_rate": metrics["complete_evidence_rate"],
                        "mean_latency_ms": output["latency_ms"]["mean"],
                        "retrieval_errors": summary["retrieval_errors"],
                    }
                )

    return rows


def write_comparison(rows: list[dict]) -> str:
    path = RESULT_DIRECTORY / f"v3-compare-{datetime.now():%Y%m%d-%H%M%S}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset_id")
    parser.add_argument("--config", action="append", required=True, help="e.g. dense, dense+bm25, dense+bm25@bm25=0.5")
    parser.add_argument("--depth", type=int, default=None, help="candidates per retriever (default: 10 for one retriever, 50 otherwise)")
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()

    configs = [parse_config(text) for text in args.config]
    outputs = []

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Same lock as the V2 evaluator: one evaluation at a time per checkout.
    with FileLock(str(DATA_DIR / "evaluation.lock"), timeout=0):
        for config in configs:
            depth = args.depth

            if depth is not None and depth < max(CUTOFFS):
                raise SystemExit(f"--depth must be at least {max(CUTOFFS)}.")

            output = run_configuration(args.dataset_id, config, depth, args.rrf_k)
            outputs.append(output)
            print(f"{config['name']}: {output['status']}  run {output['run_id']}  mean latency {output['latency_ms']['mean']} ms")

    print(f"\n{'config':<28}" + "".join(f"  HitRate@{k:<2} Recall@{k:<2}" for k in CUTOFFS))

    for output in outputs:
        metrics = output["summary"]["metrics"]
        print(f"{output['retrieval_config']['name']:<28}" + "".join(
            f"  {metrics[str(k)]['hit_rate']:>9.2f} {metrics[str(k)]['evidence_recall']:>9.2f}" for k in CUTOFFS))

    print(f"\nSaved {write_comparison(comparison_rows(outputs))}")


if __name__ == "__main__":
    main()
