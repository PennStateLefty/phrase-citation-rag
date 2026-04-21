"""CLI: chunk every parsed document into data/chunks/<document_id>.jsonl.

Usage (inside the venv):

    python scripts/chunk.py
    python scripts/chunk.py --only irs_pub_587
    python scripts/chunk.py --target-tokens 400 --overlap-tokens 40
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sentcite.chunking import chunk_parsed_dir  # noqa: E402


PARSED_DIR = REPO_ROOT / "data" / "parsed"
CHUNKS_DIR = REPO_ROOT / "data" / "chunks"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", action="append", default=[], help="Restrict to these document_ids.")
    p.add_argument("--target-tokens", type=int, default=400)
    p.add_argument("--overlap-tokens", type=int, default=40)
    args = p.parse_args()

    paths = chunk_parsed_dir(
        PARSED_DIR,
        CHUNKS_DIR,
        document_ids=args.only or None,
        target_tokens=args.target_tokens,
        overlap_tokens=args.overlap_tokens,
    )
    if not paths:
        print("No documents chunked (nothing under data/parsed/?).", file=sys.stderr)
        return 1
    for doc_id, path in paths.items():
        with path.open() as f:
            chunks = [json.loads(line) for line in f]
        total_sents = sum(len(c["sentences"]) for c in chunks)
        tokens = sum(c["token_count"] for c in chunks)
        print(
            f"[ok] {doc_id:16s} chunks={len(chunks):4d} sentences={total_sents:5d} "
            f"tokens={tokens:7d} -> {path.relative_to(REPO_ROOT)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
