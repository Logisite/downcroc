from __future__ import annotations

from dataclasses import dataclass

from downcroc.cli.docs import model


@dataclass(frozen=True)
class Hit:
    page: model.Page
    line: str
    score: float


def search(pages: list[model.Page], query: str) -> list[Hit]:
    words = [word.casefold() for word in query.split() if word.strip()]
    if not words:
        return []
    hits = []
    for page in pages:
        title = page.title.casefold()
        tags = " ".join(page.tags).casefold()
        headings = " ".join(page.headings).casefold()
        body = page.body.casefold()
        score = 0.0
        line = page.description or page.title
        for word in words:
            if title == word:
                score += 100
            elif word in title:
                score += 40
            if word in headings:
                score += 20
            if word in tags:
                score += 15
            if word in body:
                score += 5
                line = _line(page.body, word)
            if not score:
                break
        if score:
            hits.append(Hit(page, line, score * page.search_boost))
    return sorted(hits, key=lambda item: (-item.score, item.page.title))


def _line(body: str, word: str) -> str:
    for line in body.splitlines():
        if word in line.casefold() and line.strip():
            return line.strip()[:140]
    return ""
