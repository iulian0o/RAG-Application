## V2 evaluation

Run commands from the backend directory using the backend Python environment.

Upload the corpus documents and build their indexes before evaluation.

Question sets are kept in evaluation/datasets. Source JSONL files follow the
provided Kestrel format. JSON adapters identify corpus documents by their
normalized content hashes and map reference quotes for scoring.

Run the no-context baselines:

    python -m app.evaluate_no_context kestrel
    python -m app.evaluate_no_context custom

Review baseline answers manually and record correct_without_context.

Run retrieval-only evaluation:

    python -m app.evaluation_v2 kestrel
    python -m app.evaluation_v2 custom

Generate grounded answers as part of a run:

    python -m app.evaluation_v2 kestrel --generate-answers --answer-top-k 5

Results are saved under evaluation/results using unique run IDs.

Retrieval is measured at k = 1, 3, 5, 10, overall and by question type.
Unanswerable questions are excluded from retrieval denominators.
Retrieval errors count as misses and are reported separately.

Do not modify documents, indexes, or question sets during an evaluation.
Runs detecting changed inputs are invalid.

A file left with status running after a forced process termination is
incomplete. Start a fresh run and exclude the incomplete file from analysis.

The API exposes:

- GET /api/evaluation/datasets
- POST /api/evaluation/runs
- GET /api/evaluation/runs/{run_id}

POST waits for completion. The request defaults to retrieval only.
Optional answer generation increases execution time.

Run the backend with one worker, matching the existing indexing lock design.

Human grading rules are in evaluation/grading-rules.md.
Grades and diagnosis notes are added to the corresponding results file.

## Using Words and Evaluation

Run the backend on port 8000 and the frontend with npm run dev from frontend.
Open the URL printed by Vite.

Select uploaded and indexed documents, then open Words. Corpus mode shows
word frequencies and matching chunks. Question mode analyzes typed questions
or questions loaded from the evaluation sets.

Open Evaluation and load the available corpora. Select a corpus and run the
evaluation. Enable Generate answers when you want grounded answers alongside
retrieval results. Use the run ID to reopen saved results or download the JSON.

## Using Ask with retrievers (V3)

Open the Ask view, select at least one indexed document, then choose the
retrievers: **Dense**, **BM25** and **Concept Graph**. They can be combined.
With several retrievers, the backend fuses their rankings with reciprocal
rank fusion (RRF) and only the fused top-k passages reach the model.
An empty retriever selection is rejected.

Each supporting passage shows:

- its fused rank (`#1`) and the rank each retriever gave it
  (for example `dense: 2 · bm25: 1`);
- the cosine distance, only when Dense found the passage;
- for Concept Graph results, the entity matched in the question, each edge
  traversed (subject, relation, object) and the source quote of each edge.

The line under the answer lists the retrievers, candidate depth and RRF k
used for that answer.

### Concept Graph

The graph exists only for the indexed Kestrel documents. Build it from the
`backend` directory with the backend environment active:

```powershell
python -m app.build_concept_graph kestrel
```

This calls the LLM provider and consumes tokens. Inspect ranked paths in the
existing graph without rebuilding:

```powershell
python -m app.build_concept_graph kestrel --question "SVC-ORBIT"
```

If the Ask view reports that the graph is missing or stale (for example after
re-indexing), rebuild it, or uncheck Concept Graph to use Dense and BM25 only.

### Evaluation view

Open a saved run by its ID. The **Retrieval configuration** section shows the
retrievers, fusion mode, weights, RRF k, candidate depth and Git commit recorded
in the run. Runs that did not record a configuration say so.