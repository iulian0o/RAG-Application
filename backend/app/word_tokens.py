import re
import unicodedata


TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[-_'][^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'").casefold()
    return TOKEN_PATTERN.findall(normalized)


def normalize_word(value: str) -> str:
    tokens = tokenize(value)

    if len(tokens) != 1:
        raise ValueError("Enter exactly one word or identifier.")

    return tokens[0]