import json

import pytest

from app import concept_graph
from app.word_chunks import WordChunk


def test_extract_and_explain_two_hop_path(tmp_path, monkeypatch):
    first = "Aurora Reports dispatches scheduled report jobs to service SVC-ORBIT."
    second = "SVC-ORBIT processes jobs in region EU-FR2 and is owned by Indigo Operations."
    chunks = [
        WordChunk(
            chunk_id=f"index-{position}:0", document_id=str(position), index_id=f"index-{position}",
            filename=f"{position}.md", content_hash="fixture", chunk_index=0,
            start=10, end=10 + len(quote), text=quote,
        )
        for position, quote in enumerate((first, second))
    ]

    def triple(subject, subject_type, relation, target, target_type, quote):
        return {
            "subject": {"kind": subject_type, "name": subject},
            "relation": relation,
            "object": {"kind": target_type, "name": target},
            "quote": quote,
        }

    def extract(text):
        records = (
            [triple("Aurora Reports", "feature", "dispatches_to", "SVC-ORBIT", "service", first), 42]
            if text == first else
            [triple("SVC-ORBIT", "service", "owned_by", "Indigo Operations", "team", second),
             triple("SVC-ORBIT", "service", "processes_in", "EU-FR2", "region", second + " fabricated")]
        )
        return json.dumps({"triples": records}), 10, 5, False

    indexes = {chunk.document_id: {"index_id": chunk.index_id} for chunk in chunks}
    graph = concept_graph.extract_graph(chunks, indexes, "fixture", extract)
    assert graph.stats.llm_calls == 2
    assert graph.stats.input_tokens == 20
    assert graph.stats.rejected_triples == 2
    assert graph.stats.merged_entity_mentions == 1
    assert all(node.sources for node in graph.nodes)

    matches = concept_graph.retrieve_graph(graph, "Who owns the Aurora Reports service?", ["0", "1"], 5)
    assert [match.chunk_id for match in matches] == ["index-0:0", "index-1:0"]
    path = matches[0].paths[0]
    assert path.matched_entity.name == "Aurora Reports"
    assert [edge.relation for edge in path.edges] == ["dispatches_to", "owned_by"]
    assert [edge.sources[0].quote for edge in path.edges] == [first, second]
    assert [edge.sources[0].start for edge in path.edges] == [10, 10]
    assert path.traversed_reverse == [False, False]

    reverse = concept_graph.retrieve_graph(graph, "Which feature uses Indigo Operations?", ["0", "1"], 5)
    assert reverse[0].paths[0].traversed_reverse == [True, True]
    assert concept_graph.retrieve_graph(graph, "SVC-ORBITAL", ["0", "1"], 5) == []
    scoped = concept_graph.retrieve_graph(graph, "Aurora Reports", ["0"], 5)
    assert [match.chunk_id for match in scoped] == ["index-0:0"]

    artifact = tmp_path / "graph.json"
    concept_graph.write_graph(artifact, graph)
    monkeypatch.setattr(concept_graph, "active_indexes", lambda _: indexes)
    assert concept_graph.load_graph(artifact).artifact_id == graph.artifact_id
    monkeypatch.setattr(concept_graph, "active_indexes", lambda _: {"0": {"index_id": "rebuilt"}})
    with pytest.raises(ValueError, match="stale"):
        concept_graph.load_graph(artifact)
