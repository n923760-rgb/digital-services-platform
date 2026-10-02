"""Small summarization boundary: direct calls, no queue and no provider SDK in the domain."""

import re
from collections import Counter
from typing import Protocol

MAX_TEXT_CHARACTERS = 4000
MAX_SUMMARY_CHARACTERS = 1800
TEXT_INPUT_SCHEMA = {"max_characters": MAX_TEXT_CHARACTERS}
SLUG = "summarize-text"


class InvalidSummaryInput(ValueError):
    pass


class SummaryProviderError(RuntimeError):
    pass


class Summarizer(Protocol):
    async def summarize(self, text: str) -> str: ...


def validate_text(text: str) -> str:
    if not isinstance(text, str):
        raise InvalidSummaryInput("text_required")
    text = text.strip()
    if not 20 <= len(text) <= MAX_TEXT_CHARACTERS or not any(c.isalpha() for c in text):
        raise InvalidSummaryInput("text_length_or_content")
    return text


def validate_summary(result: str) -> str:
    if not isinstance(result, str) or not result.strip() or len(result) > MAX_SUMMARY_CHARACTERS:
        raise SummaryProviderError("invalid_summary_output")
    return result.strip()


class LocalSummarizer:
    """Extract original sentences; this is not a generative AI or a quality guarantee."""

    async def summarize(self, text: str) -> str:
        text = validate_text(text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?؟؛])\s+|\n+", text) if s.strip()]
        tokens = [re.findall(r"[^\W\d_]{3,}", s.casefold()) for s in sentences]
        stop = {"في", "من", "إلى", "على", "هذا", "هذه", "التي", "الذي", "كان", "ذلك",
                "the", "and", "for", "with", "that", "this"}
        frequencies = Counter(word for words in tokens for word in words if word not in stop)
        scores = [sum(frequencies[w] for w in words if w not in stop) / max(len(words), 1)
                  for words in tokens]
        selected = sorted(sorted(range(len(sentences)), key=lambda i: (-scores[i], i))[:3])
        result = "\n".join(sentences[i] for i in selected)
        if len(result) > MAX_SUMMARY_CHARACTERS:
            cut = result[:MAX_SUMMARY_CHARACTERS - 1]
            boundary = cut.rfind(" ")
            result = (cut[:boundary] if boundary > 0 else cut) + "…"
        return validate_summary(result)
