# Synthetic Kestrel benchmark

## Provenance

This is a team-requested, AI-generated substitute for the unavailable Kestrel material mentioned in the V2 assignment. It was created on 10 November 2026. All company facts, product names, limits, policies, service ownership, and operational identifiers are fictional. Describe its provenance in the team's own report. Its scores cannot be directly compared with scores obtained on the instructor's unavailable dataset.

The original starter-question schema was unavailable. The source JSONL therefore uses the local evaluator's question schema. This is an explicitly documented substitute format. Each line has id, type, question, answerable, expected_answer, and evidence fields. Each evidence item has document, quote, and start fields. The adapter contains the same questions plus the dataset name, source filename, and document content hashes.

## Upload these five files

The corpus is in docs/kestrel, relative to the repository root.

| Document key | Filename |
|---|---|
| product-guide | product-guide.md |
| billing-policies | billing-policies.md |
| error-runbook | error-runbook.md |
| service-catalog | service-catalog.md |
| security-and-support | security-and-support.md |

Upload the five Markdown files through the existing document UI. The adapter hashes were computed using the upload API's normalization rules, so the uploaded files should match without manual hash replacement. Editing a document changes its hash and may invalidate evidence offsets. Keep these files fixed during configuration comparisons.

The corpus contains 31,127 characters. The current application chunker produces 44 chunks with chunk_size 800 and overlap 80, or 36 chunks with chunk_size 1000 and overlap 100. Both are suitable starting configurations for the required comparison. Build all five documents with the same chosen settings for each run.

Upload the knowledge-base Markdown files only as the benchmark corpus. The source questions, adapter, and this setup document belong to evaluation tooling. Including reference answers in the indexed corpus would contaminate the evaluation.

## Ten questions

| IDs | Type | Purpose |
|---|---|---|
| 01, 02 | exact identifier | Distinguish KST-427 from KST-472 and SVC-GLINT from SVC-GLIDE |
| 03, 04 | split answer | Combine product requirements with security or billing rules |
| 05, 06 | different vocabulary | Map phone to voice callbacks and locked out to suspended sign-in |
| 07 | two versions | Apply the trial policy using its effective date |
| 08 | two hops | Follow Aurora Reports to its service, then find region and owner |
| 09, 10 | not in the corpus | Abstain on an undocumented founder birth date and IPv6 range |

Full IDs use the kestrel-syn- prefix. Eight questions have reference evidence and two are unanswerable. There are twelve evidence passages. The words phone and locked do not occur in the knowledge base, providing examples for Words-mode diagnosis. They are not guaranteed to cause retrieval misses.

The two-hop question has evidence in separate documents. A retrieval or generation model may still solve it without an explicit multi-stage algorithm. Its label describes the evidence relationship, not a claim about the model's internal reasoning.

## Validate after upload

From backend, with the backend Python environment active, run the following PowerShell block.

```powershell
@'
from app.evaluation_datasets import read_dataset, resolve_dataset

dataset, _ = read_dataset('kestrel')
documents, questions = resolve_dataset(dataset)
print(f'PASS: {len(documents)} documents, {len(questions)} questions')
'@ | python -
```

Expected output is five documents and ten questions. A missing-document error means that a file was not uploaded or its content differs from the version used to compute the adapter hash.

## Run the baseline and evaluation

Configure the existing Gemini environment settings before baseline or answer generation. The no-context run does not require indexes.

```powershell
python -m app.evaluate_no_context kestrel
```

Review the answers and fill the baseline's human-review fields. Preserve the dataset while comparing retrieval settings. If a question is replaced, record the revision and rerun the baseline for the revised set.

After building all five indexes, run retrieval-only evaluation.

```powershell
python -m app.evaluation_v2 kestrel
```

For the chosen configuration, request answers explicitly.

```powershell
python -m app.evaluation_v2 kestrel --generate-answers --answer-top-k 5
```

Write grading rules before grading the answers. Operational errors should be investigated before treating a run as a valid configuration comparison. Verify actual index metadata in each result file rather than relying on filenames to identify configurations.

## Checks performed during generation

The existing Pydantic loader accepted the adapter. Source JSONL and adapter questions matched exactly. All document hashes matched normalized upload content. All twelve evidence quotes were unique and matched their recorded character offsets. The existing resolve_dataset function resolved all five documents and ten questions against an isolated in-memory database.

No live application documents or indexes were created as part of these checks. No model baseline, retrieval measurements, or human grades were fabricated. These experiments remain to be run through the application.
