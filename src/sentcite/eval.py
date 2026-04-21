"""Citation evaluation: sentence-level precision / recall / F1.

Given a CitedAnswer and a GroundTruthItem, score how well the predicted
citations match the gold citations. Per answer sentence we compare the
*set* of cited source sentence_ids to the gold set, then micro-average
across the answer.
"""

from __future__ import annotations

from .schema import CitedAnswer, EvalResult, GroundTruthItem


def score_citations(pred: CitedAnswer, gt: GroundTruthItem) -> EvalResult:
    raise NotImplementedError


def _prf(predicted: set[str], gold: set[str]) -> tuple[float, float, float]:
    if not predicted and not gold:
        return 1.0, 1.0, 1.0
    if not predicted:
        return 0.0, 0.0, 0.0
    if not gold:
        return 0.0, 0.0, 0.0
    tp = len(predicted & gold)
    p = tp / len(predicted)
    r = tp / len(gold)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f
