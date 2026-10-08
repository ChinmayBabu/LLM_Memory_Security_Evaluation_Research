"""Deterministic answer-quality checks for controlled baseline fixtures."""

from __future__ import annotations


_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def _normalize(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    for word, digit in _NUMBER_WORDS.items():
        normalized = normalized.replace(word, digit)
    return normalized


def score_answer(answer: str, required_terms: list[str]) -> int:
    """Return 1 when every required term occurs in the normalized answer."""

    normalized = _normalize(answer)
    return int(all(_normalize(term) in normalized for term in required_terms))
