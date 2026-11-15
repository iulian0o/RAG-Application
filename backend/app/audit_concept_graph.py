"""Export a reproducible sample of ten Kestrel triples for human review."""

import argparse
import json
from pathlib import Path
from random import Random

from app.concept_graph import load_graph
from app.word_chunks import read_word_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args()
    graph = load_graph()
    if len(graph.edges) < 10:
        parser.exit(1, "The graph has fewer than ten distinct triples.\n")
    chunks = {chunk.chunk_id: chunk.text for chunk in read_word_chunks(list(graph.indexes))}
    if any(source.chunk_id not in chunks for edge in graph.edges for source in edge.sources):
        parser.exit(1, "The graph changed or became stale. Retry the audit.\n")
    edges = sorted(graph.edges, key=lambda edge: (edge.subject.key, edge.relation, edge.object.key))
    sample = []
    for edge in Random(args.seed).sample(edges, 10):
        record = edge.model_dump(mode="json")
        for source in record["sources"]:
            source["chunk_excerpt"] = chunks[source["chunk_id"]]
        sample.append({**record, "grade": None, "reason": None})
    with args.output.open("x", encoding="utf-8") as output:
        json.dump({
            "artifact_id": graph.artifact_id, "seed": args.seed,
            "build": graph.stats.model_dump(mode="json"),
            "entity_count": len(graph.nodes), "relation_count": len(graph.edges),
            "triples": sample,
        }, output, indent=2, ensure_ascii=False)
        output.write("\n")


if __name__ == "__main__":
    main()
