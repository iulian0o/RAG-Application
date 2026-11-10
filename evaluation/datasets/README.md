# Evaluation datasets

Keep the original question sets in Kestrel-format JSONL files.

The application reads a corresponding JSON adapter containing:

- A dataset name.
- The original JSONL filename.
- Every document belonging to the corpus, identified by content hash.
- Questions with stable IDs, original type labels, reference answers,
  and exact supporting quotes.

Retrieve against every document in the corpus. Reference evidence only
scores retrieval.

Use the document content hashes returned by the application's document API.
The upload API normalizes line endings before computing these hashes.

Example adapter structure:

{
  "name": "Kestrel",
  "source": "kestrel.source.jsonl",
  "documents": {
    "product-guide": {
      "content_hash": "COPY_HASH_FROM_DOCUMENT_API"
    }
  },
  "questions": [
    {
      "id": "COPY_ORIGINAL_ID",
      "type": "COPY_ORIGINAL_TYPE",
      "question": "COPY_ORIGINAL_QUESTION",
      "answerable": true,
      "expected_answer": "COPY_REFERENCE_ANSWER",
      "evidence": [
        {
          "document": "product-guide",
          "quote": "COPY_EXACT_QUOTE",
          "start": null
        }
      ]
    }
  ]
}

For a quote appearing multiple times, set start to its zero-based character
offset in the normalized stored document. Otherwise, leave start null.

Unanswerable questions have answerable false and an empty evidence list.

Keep question IDs stable. Record dataset changes in Git and freeze both
datasets during configuration comparisons.

Before running experiments, manually verify that each adapter faithfully
represents its source JSONL. Preserve the instructor's exact type labels.