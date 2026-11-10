from collections import Counter

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.word_chunks import WordChunk, read_word_chunks
from app.word_tokens import normalize_word, tokenize


router = APIRouter(prefix="/api/words", tags=["words"])


class SelectionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    document_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]

        if any(not value for value in cleaned):
            raise ValueError("Document IDs cannot be blank.")

        return list(dict.fromkeys(cleaned))


class VocabularyRequest(SelectionRequest):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


class WordRequest(SelectionRequest):
    word: str = Field(min_length=1, max_length=200)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        return normalize_word(value)


class QuestionRequest(SelectionRequest):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not tokenize(value):
            raise ValueError("The question must contain at least one word.")
        return value


class SelectionSummary(BaseModel):
    document_ids: list[str]
    index_ids: list[str]
    total_chunks: int


class WordSummary(BaseModel):
    word: str
    occurrences: int
    chunk_count: int


class VocabularyResponse(SelectionSummary):
    total_words: int
    total_occurrences: int
    offset: int
    limit: int
    words: list[WordSummary]


class ChunkMatch(BaseModel):
    chunk: WordChunk
    occurrences: int


class WordResponse(SelectionSummary):
    word: str
    occurrences: int
    chunk_count: int
    offset: int
    limit: int
    matches: list[ChunkMatch]


class ChunkCount(BaseModel):
    chunk_id: str
    occurrences: int


class QuestionWord(WordSummary):
    question_occurrences: int
    chunk_counts: list[ChunkCount]


class QuestionResponse(SelectionSummary):
    question: str
    present: list[QuestionWord]
    absent: list[str]
    chunks: list[WordChunk]


def selection_summary(
    document_ids: list[str],
    chunks: list[WordChunk],
) -> dict:
    return {
        "document_ids": document_ids,
        "index_ids": sorted({chunk.index_id for chunk in chunks}),
        "total_chunks": len(chunks),
    }


def count_chunks(chunks: list[WordChunk]) -> list[Counter]:
    return [Counter(tokenize(chunk.text)) for chunk in chunks]


@router.post("/vocabulary", response_model=VocabularyResponse)
def vocabulary(request: VocabularyRequest) -> VocabularyResponse:
    chunks = read_word_chunks(request.document_ids)
    counts = count_chunks(chunks)

    occurrences = Counter()
    chunk_frequency = Counter()

    for chunk_counts in counts:
        occurrences.update(chunk_counts)
        chunk_frequency.update(chunk_counts.keys())

    words = [
        WordSummary(
            word=word,
            occurrences=count,
            chunk_count=chunk_frequency[word],
        )
        for word, count in occurrences.items()
    ]
    words.sort(key=lambda item: (-item.occurrences, item.word))

    return VocabularyResponse(
        **selection_summary(request.document_ids, chunks),
        total_words=len(words),
        total_occurrences=sum(occurrences.values()),
        offset=request.offset,
        limit=request.limit,
        words=words[request.offset:request.offset + request.limit],
    )


@router.post("/chunks", response_model=WordResponse)
def word_chunks(request: WordRequest) -> WordResponse:
    chunks = read_word_chunks(request.document_ids)
    counts = count_chunks(chunks)

    matches = [
        ChunkMatch(chunk=chunk, occurrences=count[request.word])
        for chunk, count in zip(chunks, counts)
        if count[request.word] > 0
    ]

    return WordResponse(
        **selection_summary(request.document_ids, chunks),
        word=request.word,
        occurrences=sum(match.occurrences for match in matches),
        chunk_count=len(matches),
        offset=request.offset,
        limit=request.limit,
        matches=matches[request.offset:request.offset + request.limit],
    )


@router.post("/question", response_model=QuestionResponse)
def question_words(request: QuestionRequest) -> QuestionResponse:
    chunks = read_word_chunks(request.document_ids)
    counts = count_chunks(chunks)
    question_counts = Counter(tokenize(request.question))

    present = []
    absent = []
    matched_chunk_ids = set()

    for word, question_occurrences in question_counts.items():
        matches = [
            ChunkCount(chunk_id=chunk.chunk_id, occurrences=count[word])
            for chunk, count in zip(chunks, counts)
            if count[word] > 0
        ]

        if not matches:
            absent.append(word)
            continue

        matched_chunk_ids.update(match.chunk_id for match in matches)
        present.append(
            QuestionWord(
                word=word,
                question_occurrences=question_occurrences,
                occurrences=sum(match.occurrences for match in matches),
                chunk_count=len(matches),
                chunk_counts=matches,
            )
        )

    return QuestionResponse(
        **selection_summary(request.document_ids, chunks),
        question=request.question,
        present=present,
        absent=absent,
        chunks=[
            chunk for chunk in chunks
            if chunk.chunk_id in matched_chunk_ids
        ],
    )