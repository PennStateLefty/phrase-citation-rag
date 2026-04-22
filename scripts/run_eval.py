"""CLI: run the Phase 1a eval harness against a curated GT set.

Usage
-----

    python scripts/run_eval.py \\
        --gt data/ground_truth/synthetic/phase1a-100-qg/items_reviewed.jsonl \\
        --only-passing \\
        --out data/eval \\
        --run-id phase1a-67-$(date -u +%Y%m%d) \\
        --include-faithfulness \\
        --include-self-consistency

By default both strategies are evaluated and retrieval metadata is
recorded. ``--limit N`` truncates to the first N items (useful for
smoke runs before the full 67-item pass).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make ``src/`` importable when the script is run directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sentcite.eval import evaluate_gt_set, write_eval_report  # noqa: E402
from sentcite.layperson_review import load_reviews  # noqa: E402
from sentcite.schema import GroundTruthItem  # noqa: E402


def load_gt(path: Path, *, only_passing: bool) -> list[GroundTruthItem]:
    items: list[GroundTruthItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if only_passing:
            if not (raw.get("judge_well_formed") and raw.get("judge_supported")):
                continue
        items.append(GroundTruthItem.model_validate(raw))
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", type=Path, required=True,
                    help="Path to items_reviewed.jsonl (QG output).")
    ap.add_argument("--only-passing", action="store_true",
                    help="Keep only judge_well_formed AND judge_supported items.")
    ap.add_argument("--out", type=Path, default=Path("data/eval"),
                    help="Output root directory.")
    ap.add_argument("--run-id", default=None,
                    help="Run identifier (default: UTC timestamp).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only evaluate the first N items (smoke-run knob).")
    ap.add_argument("--strategies", nargs="+",
                    default=["inline_prompted", "post_gen_alignment"],
                    choices=["inline_prompted", "post_gen_alignment"])
    ap.add_argument("--mode", default="dual",
                    choices=["dual", "chunks", "sentences"])
    ap.add_argument("--k-sentences", type=int, default=20)
    ap.add_argument("--k-chunks", type=int, default=5)
    ap.add_argument("--tau", type=float, default=0.75)
    ap.add_argument("--top-k", type=int, default=3,
                    help="Per-answer-sentence citation cap for Strategy B.")
    ap.add_argument("--include-faithfulness", action="store_true",
                    help="Also run LLM-as-judge faithfulness per item.")
    ap.add_argument("--include-self-consistency", action="store_true",
                    help="Also measure citation stability (adds N extra gen/cite calls per item).")
    ap.add_argument("--consistency-runs", type=int, default=5)
    ap.add_argument("--consistency-temperature", type=float, default=0.7)
    ap.add_argument("--reviews", type=Path, default=None,
                    help="Path to layperson reviews.jsonl (non-SME spot-check).")
    args = ap.parse_args()

    items = load_gt(args.gt, only_passing=args.only_passing)
    if args.limit:
        items = items[: args.limit]
    if not items:
        print(f"No GT items loaded from {args.gt}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(items)} GT items (only_passing={args.only_passing})")
    print(f"Strategies: {args.strategies}")
    print(f"Enrichments: faithfulness={args.include_faithfulness} "
          f"self_consistency={args.include_self_consistency}")

    reviews = None
    if args.reviews:
        reviews = load_reviews(args.reviews)
        print(f"Loaded {len(reviews)} layperson reviews from {args.reviews}")

    def _progress(i: int, n: int, buckets) -> None:
        print(f"  [{i}/{n}] done", flush=True)

    report = evaluate_gt_set(
        items,
        strategies=tuple(args.strategies),
        retrieval_mode=args.mode,
        k_sentences=args.k_sentences,
        k_chunks=args.k_chunks,
        tau=args.tau,
        top_k=args.top_k,
        include_faithfulness=args.include_faithfulness,
        include_self_consistency=args.include_self_consistency,
        consistency_runs=args.consistency_runs,
        consistency_temperature=args.consistency_temperature,
        on_progress=_progress,
        reviews=reviews,
    )

    paths = write_eval_report(report, out_dir=args.out, run_id=args.run_id)
    print(f"\nReport written:")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    print(f"\nElapsed: {report.elapsed_seconds:.1f}s")
    print(f"\n{report.to_markdown_table()}")


if __name__ == "__main__":
    main()
