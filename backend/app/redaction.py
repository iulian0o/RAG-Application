
import re
from collections import Counter


POLICY_VERSION = "v1"

EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.-])"
    r"\d{2,4}[\s.-]\d{2,4}"
    r"(?:[\s.-]\d{2,4})?(?!\w)"
)

# Conservative name detection: names explicitly introduced by a label.
NAME_RE = re.compile(
    r"(?i:\b(?:full name|name|my name is|contact|nom|"
    r"prénom|je m'appelle)\s*[:\-]?\s+)"
    r"(?P<name>[A-ZÀ-ÖØ-Þ][^\W\d_’'-]*"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][^\W\d_’'-]*){1,2})"
)


class RedactionError(Exception):
    """Raised when personal-data redaction cannot be completed."""


class RedactionSession:
    def __init__(self):
        self._placeholders = {}
        self._counts = Counter()

    def _replace(self, entity_type, value):
        key = (entity_type, value.casefold())

        if key not in self._placeholders:
            number = sum(
                1 for existing_type, _ in self._placeholders
                if existing_type == entity_type
            ) + 1

            self._placeholders[key] = f"[{entity_type}_{number}]"
            self._counts[entity_type] += 1

        return self._placeholders[key]

    def redact(self, text):
        if not isinstance(text, str):
            raise RedactionError("Expected text input for redaction")

        try:
            text = EMAIL_RE.sub(
                lambda match: self._replace("EMAIL", match.group()),
                text,
            )
            text = PHONE_RE.sub(
                lambda match: self._replace("PHONE", match.group()),
                text,
            )
            text = NAME_RE.sub(
                lambda match: match.group().replace(
                    match.group("name"),
                    self._replace("PERSON", match.group("name")),
                ),
                text,
            )
            return text
        except Exception as exc:
            raise RedactionError("Personal-data redaction failed") from exc

    def summary(self):
        return {
            "policy_version": POLICY_VERSION,
            "counts_by_entity_type": dict(self._counts),
        }
