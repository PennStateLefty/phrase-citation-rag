"""CLI: run the pipeline against a public sentence-attribution benchmark.

    python scripts/run_benchmark.py \\
        --format hagrid \\
        --input data/benchmarks/hagrid/dev.jsonl \\
        --out data/eval \\
        --run-id hagrid-20  --limit 20

The input file is the vendor-published JSONL (HAGRID or ALCE). We
don't redistribute it — the loader expects the user to drop the file
under ``data/benchmarks/<name>/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sentcite.benchmarks import (  # noqa: E402
    evaluate_benchmark,
    load_alce_jsonl,
    load_hagrid_jsonl,
)
from sentcite.eval import write_eval_report  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["hagrid", "alce"], required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/eval"))
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--strategies", nargs="+",
                    default=["inline_prompted", "post_gen_alignment"],
                    choices=["inline_prompted", "post_gen_alignment"])
    ap.add_argument("--tau", type=float, default=0.75)
    ap.add_argument("--top-k", type=int, default=3)
    args = ap.parse_args()

    loader = load_hagrid_jsonl if args.format == "hagrid" else load_alce_jsonl
    items = list(loader(args.input, limit=args.limit))
    if not items:
        print(f"No items loaded from {args.input} ({args.format})", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(items)} items ({args.format})")
    print(f"Strategies: {args.strategies}")

    def _progress(i, n, buckets):
        print(f"  [{i}/{n}] done", flush=True)

    report = evaluate_benchmark(
        items,
        strategies=tuple(args.strategies),
        tau=args.tau,
        top_k=args.top_k,
        on_progress=_progress,
    )

    run_id = args.run_id or f"{args.format}-run"
    paths = write_eval_report(report, out_dir=args.out, run_id=run_id)
    print("\nReport written:")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    print(f"\nElapsed: {report.elapsed_seconds:.1f}s")
    print(f"\n{report.to_markdown_table()}")


if __name__ == "__main__":
    main()
