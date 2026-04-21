"""CLI: (re)create the chunks index and upload chunks+embeddings.

Usage (inside the venv):

    python scripts/build_index.py --recreate         # drop + recreate schema, upload all
    python scripts/build_index.py                    # upsert into existing index
    python scripts/build_index.py --only irs_pub_587 # only one doc
    python scripts/build_index.py --ensure-only      # just create/update index schema
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sentcite.config import AzureConfig  # noqa: E402
from sentcite.indexing import ensure_chunks_index, load_chunks_from_jsonl, upload_chunks  # noqa: E402


CHUNKS_DIR = REPO_ROOT / "data" / "chunks"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recreate", action="store_true", help="Drop and recreate the index before upload.")
    p.add_argument("--ensure-only", action="store_true", help="Create/update index schema; skip upload.")
    p.add_argument("--only", action="append", default=[], help="Restrict upload to these document_ids.")
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--embed-batch-size", type=int, default=64)
    args = p.parse_args()

    cfg = AzureConfig.from_env()

    name = ensure_chunks_index(cfg, recreate=args.recreate)
    print(f"[index] ensured {name!r} (recreate={args.recreate})")
    if args.ensure_only:
        return 0

    files = sorted(CHUNKS_DIR.glob("*.jsonl"))
    if args.only:
        keep = set(args.only)
        files = [f for f in files if f.stem in keep]
    if not files:
        print(f"No chunk files in {CHUNKS_DIR} (or --only filtered everything).", file=sys.stderr)
        return 1

    grand_totals = {"chunks": 0, "sentences": 0}
    for path in files:
        chunks = load_chunks_from_jsonl(path)
        t0 = time.perf_counter()
        counts = upload_chunks(
            chunks,
            cfg=cfg,
            batch_size=args.batch_size,
            embed_batch_size=args.embed_batch_size,
        )
        dt = time.perf_counter() - t0
        grand_totals["chunks"] += counts["chunks"]
        grand_totals["sentences"] += counts["sentences"]
        print(
            f"[upload] {path.stem:16s} chunks={counts['chunks']:4d} "
            f"sentences={counts['sentences']:5d} elapsed={dt:6.1f}s"
        )
    print(f"[done] chunks={grand_totals['chunks']} sentences={grand_totals['sentences']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
