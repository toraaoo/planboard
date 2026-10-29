"""Fuzzy search over plans: every query word must match a word of the text, closely.

A word matches exactly, as a prefix or substring, or within a few typos (difflib's
ratio). Hits are ranked by how well they match, then by where: titles and ids before
summaries, summaries before section content.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from .json import JsonValue
from .plan import Plan

Kind = Literal["plan", "task", "section", "diagram"]

CUTOFF = 0.75  # the lowest difflib ratio that counts as a typo, not another word
_NOT_PROSE = frozenset({"type", "ref", "tone", "language", "ordered"})
_WORD = re.compile(r"[\w-]+")
_AROUND = 40
_WEIGHTS = {"id": 1.0, "title": 1.0, "alt": 0.9, "summary": 0.9, "note": 0.9}


@dataclass(frozen=True, slots=True)
class Hit:
    ref: str
    kind: Kind
    title: str
    field: str
    snippet: str
    score: float


def search(plans: Mapping[str, Plan], query: str) -> list[Hit]:
    """The best hit per plan, task, section or diagram, best first."""
    terms = [term.casefold() for term in _WORD.findall(query)]
    if not terms:
        return []
    best: dict[str, Hit] = {}
    for plan_id, plan in plans.items():
        for ref, kind, title, field, text in _texts(plan_id, plan):
            line = " ".join(text.split())
            found = _match(terms, line)
            if found is None:
                continue
            score, start, length = found
            score *= _WEIGHTS.get(field, 0.8)
            if ref not in best or score > best[ref].score:
                snippet = _snippet(line, start, length)
                best[ref] = Hit(ref, kind, title, field, snippet, round(score, 3))
    return sorted(best.values(), key=lambda hit: -hit.score)


def _match(terms: list[str], line: str) -> tuple[float, int, int] | None:
    """The mean score of the terms and where the first matched, if all match."""
    folded = line.casefold()
    words = [(m.start(), m.group()) for m in _WORD.finditer(folded)]
    scores: list[float] = []
    first: tuple[int, int] | None = None
    for term in terms:
        score, where = _term(term, folded, words)
        if score < CUTOFF:
            return None
        scores.append(score)
        first = first or where
    start, length = first or (0, 0)
    return sum(scores) / len(scores), start, length


def _term(
    term: str, folded: str, words: list[tuple[int, str]]
) -> tuple[float, tuple[int, int]]:
    best = (0.0, (0, 0))
    for start, word in words:
        if word == term:
            return 1.0, (start, len(word))
        if word.startswith(term):
            score = 0.95
        elif term in word:
            score = 0.9
        else:
            # Compare with the word, and with its start, so a typo in a prefix counts.
            score = max(_ratio(term, word), _ratio(term, word[: len(term)]) - 0.05)
        if score > best[0]:
            best = (score, (start, len(word)))
    if best[0] < 0.9 and term in folded:  # a phrase across words, such as "e-mail"
        return 0.9, (folded.index(term), len(term))
    return best


def _ratio(a: str, b: str) -> float:
    matcher = SequenceMatcher(None, a, b)
    if matcher.real_quick_ratio() < CUTOFF or matcher.quick_ratio() < CUTOFF:
        return 0.0
    return matcher.ratio()


def _texts(plan_id: str, plan: Plan) -> Iterator[tuple[str, Kind, str, str, str]]:
    yield plan_id, "plan", plan.title, "id", plan_id
    yield plan_id, "plan", plan.title, "title", plan.title
    yield plan_id, "plan", plan.title, "summary", plan.summary
    for task in plan.tasks:
        ref = f"{plan_id}#{task.id}"
        yield ref, "task", task.title, "id", task.id
        yield ref, "task", task.title, "title", task.title
        for field in ("summary", "note"):
            value = getattr(task, field)
            if value:
                yield ref, "task", task.title, field, value
    for section in plan.sections:
        ref = f"{plan_id}#{section.id}"
        yield ref, "section", section.title, "id", section.id
        yield ref, "section", section.title, "title", section.title
        for number, block in enumerate(section.blocks, start=1):
            dumped = block.model_dump(mode="json", exclude_none=True)
            for text in _prose(dumped):
                yield ref, "section", section.title, f"block {number}", text
    for diagram_id, diagram in plan.diagrams.items():
        ref = f"{plan_id}#{diagram_id}"
        yield ref, "diagram", diagram.alt, "id", diagram_id
        yield ref, "diagram", diagram.alt, "alt", diagram.alt
        if diagram.source:
            yield ref, "diagram", diagram.alt, "source", diagram.source


def _prose(value: JsonValue) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _prose(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in _NOT_PROSE:
                yield from _prose(item)


def _snippet(line: str, start: int, length: int) -> str:
    left = max(start - _AROUND, 0)
    right = min(start + length + _AROUND, len(line))
    return f"{'…' if left else ''}{line[left:right]}{'…' if right < len(line) else ''}"
