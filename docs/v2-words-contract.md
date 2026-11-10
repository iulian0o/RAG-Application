# V2 Words API

## Selection

Every request includes document_ids containing the selected corpus documents.
All selected documents must have current indexes.

## Tokenization

- Normalize Unicode using NFKC and compare using casefold.
- Keep accented letters and numbers.
- Keep internal apostrophes, hyphens, and underscores.
- Convert curly apostrophes to straight apostrophes.
- Preserve identifiers such as ERR-401 as one token.
- Keep stopwords.
- Apply the same tokenizer to chunks, questions, and word lookups.
- Do not apply stemming or synonym expansion.

## Counts

occurrences is the total number of occurrences in the selected indexed chunks.

chunk_count is the number of distinct chunks containing the word.

Overlapping text contributes once for every chunk containing it.
These counts describe indexed chunks, so overlap can increase occurrences.

The existing chunker can split words at character boundaries.
Tokenize each stored chunk as it exists. Boundary fragments can therefore
appear in the vocabulary.

## Endpoints

POST /api/words/vocabulary
Request:
{
  "document_ids": ["document-id"],
  "offset": 0,
  "limit": 100
}

POST /api/words/chunks
Request:
{
  "document_ids": ["document-id"],
  "word": "ERR-401",
  "offset": 0,
  "limit": 50
}

POST /api/words/question
Request:
{
  "document_ids": ["document-id"],
  "question": "Why am I locked out?"
}

Vocabulary ordering is descending occurrence count, then alphabetical word.
Chunk ordering is document ID, then chunk position.
Question words preserve their first-appearance order after normalization.

Responses include active index IDs. Refresh the Words views after rebuilding
indexes or changing document selection.

## Errors

404 means a selected document no longer exists.
409 means an index is missing, outdated, empty, or currently busy.
422 means the request is invalid.
503 means stored chunks could not be read consistently.

## Frontend ownership

Person C owns the Words tab, selection controls, loading/error states, and
question-set picker.

The question endpoint accepts question text. Person C can pass either typed
text or text selected from Person A's dataset endpoint.

Run the backend as one process, consistent with its existing indexing lock.