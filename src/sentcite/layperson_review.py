"""Layperson review of synthetic ground-truth items.

Phase-1a bridge between "synthetic GT generated and self-judged by
LLMs" and "SME-validated GT". A non-SME reviewer (ML Eng + PM) spot-
checks a subset of items for obvious breakage — malformed questions,
gold answers that clearly don't match the cited span, citations that
point at the wrong section — and tags each with a confidence rating.

This is **not** SME validation. The rating is surfaced as a separate
column everywhere it appears so readers don't conflate it with domain
sign-off.

Schema (one JSON object per line):

    {
      "question_id": "qa-00042",
      "reviewer": "jgutherie",
      "reviewer_role": "ml-engineer",  // or "pm", "other"
      "confidence": "high",             // "high" | "medium" | "low"
      "flags": ["citation_mismatch"],   // optional controlled vocab
      "notes": "Gold cites Pub 587 p.12 but the quoted sentence is on p.14.",
      "reviewed_at": "2026-04-22T16:53:00Z"
    }
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

Confidence = Literal["high", "medium", "low"]
ReviewerRole = Literal["ml-engineer", "pm", "other"]

VALID_CONFIDENCE: tuple[Confidence, ...] = ("high", "medium", "low")
VALID_ROLES: tuple[ReviewerRole, ...] = ("ml-engineer", "pm", "other")

FLAG_VOCAB: tuple[str, ...] = (
    "question_unclear",
    "question_not_answerable",
    "gold_answer_wrong",
    "gold_answer_incomplete",
    "citation_mismatch",
    "citation_insufficient",
    "out_of_scope",
    "other",
)


@dataclass(frozen=True)
class LaypersonReview:
    question_id: str
    reviewer: str
    reviewer_role: ReviewerRole
    confidence: Confidence
    flags: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(
                f"confidence must be one of {VALID_CONFIDENCE}, got {self.confidence!r}"
            )
        if self.reviewer_role not in VALID_ROLES:
            raise ValueError(
                f"reviewer_role must be one of {VALID_ROLES}, got {self.reviewer_role!r}"
            )
        # Populate reviewed_at if not given. Have to use object.__setattr__
        # because the dataclass is frozen.
        if not self.reviewed_at:
            object.__setattr__(
                self,
                "reviewed_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flags"] = list(self.flags)
        return d


def load_reviews(path: str | Path) -> dict[str, LaypersonReview]:
    """Load a reviews.jsonl file. Last-write-wins per question_id."""
    p = Path(path)
    out: dict[str, LaypersonReview] = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        rev = LaypersonReview(
            question_id=rec["question_id"],
            reviewer=rec.get("reviewer", "unknown"),
            reviewer_role=rec.get("reviewer_role", "other"),
            confidence=rec["confidence"],
            flags=tuple(rec.get("flags", [])),
            notes=rec.get("notes", ""),
            reviewed_at=rec.get("reviewed_at", ""),
        )
        out[rev.question_id] = rev
    return out


def append_review(path: str | Path, review: LaypersonReview) -> None:
    """Append a single review to the JSONL file, creating parent dirs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(review.to_dict()) + "\n")


def write_reviews(path: str | Path, reviews: Iterable[LaypersonReview]) -> None:
    """Bulk write — overwrites the file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for r in reviews:
            f.write(json.dumps(r.to_dict()) + "\n")


def summarize_reviews(
    reviews: dict[str, LaypersonReview],
) -> dict[str, int | dict[str, int]]:
    """Return counts by confidence and top flags. Used in eval reports."""
    by_conf: dict[str, int] = {c: 0 for c in VALID_CONFIDENCE}
    flag_counts: dict[str, int] = {}
    for r in reviews.values():
        by_conf[r.confidence] += 1
        for fl in r.flags:
            flag_counts[fl] = flag_counts.get(fl, 0) + 1
    return {
        "total": len(reviews),
        "by_confidence": by_conf,
        "flag_counts": dict(sorted(flag_counts.items(), key=lambda kv: -kv[1])),
    }
