"""Interactive CLI for layperson review of synthetic GT items.

Walks a reviewer through 10–20 items, showing question / gold answer /
citation spans, and collects a confidence rating + optional flags and
notes. Results go to a JSONL sidecar that ``scripts/run_eval.py
--reviews`` threads into the report.

    python scripts/review_gt.py \\
        --gt data/ground_truth/synthetic/phase1a-100-qg/items_reviewed.jsonl \\
        --out data/ground_truth/synthetic/phase1a-100-qg/reviews.jsonl \\
        --reviewer jgutherie --role ml-engineer \\
        --sample 15 --resume

- ``--resume`` skips items already present in the output file.
- ``--sample N`` picks a random sample (seeded for reproducibility via
  ``--seed``). Omit to walk every item.
- Only items passing the self-judge (well-formed AND supported) are
  offered by default; pass ``--include-failing`` to review everything.

Controls per item:

  Confidence: [h]igh / [m]edium / [l]ow / [s]kip / [q]uit
  Flags: comma-separated from the FLAG_VOCAB (or blank)
  Notes: free text (or blank)

Clearly **non-SME**. The review captures "does this look obviously
broken?", not "is this tax-law correct?".
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sentcite.layperson_review import (  # noqa: E402
    FLAG_VOCAB,
    LaypersonReview,
    append_review,
    load_reviews,
    summarize_reviews,
)

CONFIDENCE_MAP = {"h": "high", "m": "medium", "l": "low"}


def _load_items(path: Path, *, include_failing: bool) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not include_failing:
            if not (rec.get("judge_well_formed") and rec.get("judge_supported")):
                continue
        out.append(rec)
    return out


def _render_item(rec: dict) -> str:
    lines = [
        "",
        "=" * 78,
        f"question_id : {rec.get('question_id')}",
        f"difficulty  : {rec.get('difficulty')}",
        f"source doc  : {rec.get('document_id')}  (page {rec.get('page')})",
        "",
        f"Q: {rec.get('question')}",
        "",
        f"Gold answer:",
        f"  {rec.get('gold_answer')}",
        "",
        f"Source span sids : {rec.get('source_span_sentence_ids')}",
        f"Gold citations   : {rec.get('gold_citations')}",
    ]
    union = rec.get("union_additions") or []
    if union:
        lines.append(f"Union additions  : {union}")
    reasons = rec.get("judge_reasons") or []
    if reasons:
        lines.append("Judge notes:")
        for r in reasons:
            lines.append(f"  - {r}")
    lines.append("=" * 78)
    return "\n".join(lines)


def _prompt_confidence() -> str | None:
    while True:
        raw = input("Confidence [h/m/l/s=skip/q=quit]: ").strip().lower()
        if raw in ("q", "quit"):
            return None
        if raw in ("s", "skip"):
            return "skip"
        if raw in CONFIDENCE_MAP:
            return CONFIDENCE_MAP[raw]
        print("  please enter h, m, l, s, or q")


def _prompt_flags() -> tuple[str, ...]:
    print(f"  Available flags: {', '.join(FLAG_VOCAB)}")
    raw = input("Flags (comma-separated, blank=none): ").strip()
    if not raw:
        return ()
    chosen = [f.strip() for f in raw.split(",") if f.strip()]
    valid = []
    for f in chosen:
        if f in FLAG_VOCAB:
            valid.append(f)
        else:
            print(f"  (ignoring unknown flag: {f!r})")
    return tuple(valid)


def _prompt_notes() -> str:
    return input("Notes (blank=none): ").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True,
                    help="JSONL sidecar for reviews.")
    ap.add_argument("--reviewer", required=True,
                    help="Reviewer alias (e.g. 'jgutherie').")
    ap.add_argument("--role", choices=["ml-engineer", "pm", "other"],
                    required=True)
    ap.add_argument("--sample", type=int, default=None,
                    help="Randomly sample N items (default: all).")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true",
                    help="Skip items already present in --out.")
    ap.add_argument("--include-failing", action="store_true",
                    help="Also offer items that failed the self-judge.")
    args = ap.parse_args()

    items = _load_items(args.gt, include_failing=args.include_failing)
    if not items:
        print(f"No items loaded from {args.gt}", file=sys.stderr)
        sys.exit(1)

    if args.sample and args.sample < len(items):
        rng = random.Random(args.seed)
        items = rng.sample(items, args.sample)

    already: set[str] = set()
    if args.resume:
        already = set(load_reviews(args.out).keys())
        if already:
            items = [r for r in items if r.get("question_id") not in already]
            print(f"Resuming: {len(already)} items already reviewed — "
                  f"{len(items)} remaining.")

    if not items:
        print("Nothing to review.")
        return

    print(f"\nReviewing {len(items)} items as {args.reviewer} ({args.role}).\n"
          f"Non-SME spot check — flag obvious breakage only.\n")

    reviewed = 0
    for rec in items:
        print(_render_item(rec))
        conf = _prompt_confidence()
        if conf is None:
            print("\nQuitting early.")
            break
        if conf == "skip":
            print("(skipped)")
            continue
        flags = _prompt_flags()
        notes = _prompt_notes()
        review = LaypersonReview(
            question_id=rec["question_id"],
            reviewer=args.reviewer,
            reviewer_role=args.role,
            confidence=conf,  # type: ignore[arg-type]
            flags=flags,
            notes=notes,
        )
        append_review(args.out, review)
        reviewed += 1
        print(f"  recorded ({reviewed} this session).")

    # Final summary.
    all_reviews = load_reviews(args.out)
    s = summarize_reviews(all_reviews)
    print("\n" + "=" * 40)
    print(f"Reviews file: {args.out}")
    print(f"Total reviewed: {s['total']}")
    print(f"By confidence: {s['by_confidence']}")
    if s["flag_counts"]:
        print("Top flags:")
        for name, count in list(s["flag_counts"].items())[:5]:
            print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
