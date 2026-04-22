"""CLI: run quality gates on a synth-GT items.jsonl.

Usage::

    python scripts/run_quality_gates.py \\
        --items-path data/ground_truth/synthetic/phase1a-100/items.jsonl \\
        --run-id phase1a-100-qg

Writes to ``data/ground_truth/synthetic/<run_id>/`` alongside the source
run's output (by default the sibling ``<run_id>`` of the source items).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sentcite.quality_gates import run_quality_gates, write_quality_gate_run
from sentcite.synth_gt import load_corpus_chunks, load_synth_gt_items


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--items-path", type=Path, required=True)
    p.add_argument("--chunk-dir", type=Path, default=Path("data/chunks"))
    p.add_argument(
        "--out-dir", type=Path, default=Path("data/ground_truth/synthetic")
    )
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--top-k-candidates", type=int, default=20)
    p.add_argument("--max-candidates-to-judge", type=int, default=10)
    p.add_argument(
        "--include-failures-in-union",
        action="store_true",
        help="Also run the union labeler on items that failed the agreement filter.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    print(f"Loading items from {args.items_path}...", flush=True)
    items = load_synth_gt_items(args.items_path)
    print(f"  {len(items)} items loaded.", flush=True)

    print(f"Loading chunks from {args.chunk_dir}...", flush=True)
    chunks = load_corpus_chunks(args.chunk_dir)
    print(f"  {len(chunks)} chunks loaded.", flush=True)

    def on_progress(done: int, total: int, passed: int, additions: int) -> None:
        if done % max(1, total // 20) == 0 or done == total:
            print(
                f"  [{done:>4}/{total}] agreement_passed={passed} union_additions={additions}",
                flush=True,
            )

    run = run_quality_gates(
        items,
        chunks,
        top_k_candidates=args.top_k_candidates,
        max_candidates_to_judge=args.max_candidates_to_judge,
        skip_union_if_agreement_fails=not args.include_failures_in_union,
        on_progress=on_progress,
    )

    paths = write_quality_gate_run(run, out_dir=args.out_dir, run_id=args.run_id)
    print("\nDone.")
    print(f"  items:    {paths['items']}")
    print(f"  failures: {paths['failures']}")
    print(f"  manifest: {paths['manifest']}")
    print(
        f"  agreement: {run.agreement_passed}/{len(run.items)} passed, "
        f"{run.union_additions_total} union additions "
        f"in {run.elapsed_seconds:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
