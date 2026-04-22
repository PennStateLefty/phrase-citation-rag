"""CLI: generate attribution-first synthetic ground-truth items.

Usage::

    python scripts/build_synth_gt.py --count 100 --seed 7

    # smoke test (3 items, one span per difficulty)
    python scripts/build_synth_gt.py --easy 1 --medium 1 --hard 1

Writes to ``data/ground_truth/synthetic/<run_id>/`` unless ``--out-dir`` is
overridden. Prints the manifest path on completion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sentcite.synth_gt import (
    generate_synth_gt,
    load_corpus_chunks,
    select_spans,
    write_synth_gt_run,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chunk-dir", type=Path, default=Path("data/chunks"))
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/ground_truth/synthetic"),
    )
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--easy", type=int, default=40)
    p.add_argument("--medium", type=int, default=35)
    p.add_argument("--hard", type=int, default=25)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--max-tokens", type=int, default=400)
    p.add_argument(
        "--max-span-len",
        type=int,
        default=3,
        help="Cap on sentences per span (1..3 is the plan default).",
    )
    p.add_argument(
        "--count",
        type=int,
        default=None,
        help="If set, overrides --easy/--medium/--hard with a proportional split "
        "(40/35/25).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    if args.count is not None:
        # default split 40/35/25
        easy = round(args.count * 0.40)
        medium = round(args.count * 0.35)
        hard = args.count - easy - medium
        targets = {"easy": easy, "medium": medium, "hard": hard}
    else:
        targets = {"easy": args.easy, "medium": args.medium, "hard": args.hard}

    print(f"Loading chunks from {args.chunk_dir}...", flush=True)
    chunks = load_corpus_chunks(args.chunk_dir)
    print(f"  {len(chunks)} chunks loaded.", flush=True)

    spans = select_spans(
        chunks,
        target_per_difficulty=targets,
        seed=args.seed,
        max_span_len=args.max_span_len,
    )
    print(
        f"Selected {len(spans)} spans "
        f"(targets: easy={targets['easy']} medium={targets['medium']} hard={targets['hard']})",
        flush=True,
    )

    def on_progress(done: int, total: int, items, failures) -> None:
        if done % max(1, total // 20) == 0 or done == total:
            print(
                f"  [{done:>4}/{total}] items={len(items)} failures={len(failures)}",
                flush=True,
            )

    run = generate_synth_gt(
        spans,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        seed=args.seed,
        target_counts=targets,
        on_progress=on_progress,
    )

    paths = write_synth_gt_run(run, out_dir=args.out_dir, run_id=args.run_id)
    print("\nDone.")
    print(f"  items:    {paths['items']}")
    print(f"  failures: {paths['failures']}")
    print(f"  manifest: {paths['manifest']}")
    print(
        f"  {len(run.items)} items / {len(run.failures)} failures "
        f"in {run.elapsed_seconds:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
