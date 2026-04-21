"""CLI runner: upload the Phase 1 corpus to Blob and parse with Document Intelligence.

Usage (inside the venv, with .env populated):

    python scripts/ingest.py                     # upload+parse all
    python scripts/ingest.py --only irs_pub_463  # just one doc
    python scripts/ingest.py --force             # re-parse even if artifacts exist
    python scripts/ingest.py --parse-only        # skip blob upload
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from sentcite.ingest import ingest_and_parse, parse_pdf, upload_corpus  # noqa: E402

from scripts.download_corpus import CORPUS  # noqa: E402


PARSED_DIR = REPO_ROOT / "data" / "parsed"
RAW_DIR = REPO_ROOT / "data" / "raw_pdfs"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", action="append", default=[], help="Restrict to these document_ids.")
    p.add_argument("--force", action="store_true", help="Re-parse even if artifacts exist.")
    p.add_argument("--parse-only", action="store_true", help="Skip blob upload; only parse local PDFs.")
    p.add_argument("--overwrite-blob", action="store_true", help="Re-upload blobs even if they exist.")
    args = p.parse_args()

    docs = [d for d in CORPUS if not args.only or d.document_id in args.only]
    if not docs:
        print(f"No matching docs for --only={args.only}", file=sys.stderr)
        return 2

    pairs: list[tuple[str, Path]] = []
    for d in docs:
        pdf = RAW_DIR / d.filename
        if not pdf.is_file():
            print(f"[skip] {d.document_id}: {pdf} missing — run scripts/download_corpus.py first.", file=sys.stderr)
            continue
        pairs.append((d.document_id, pdf))
    if not pairs:
        return 1

    if args.parse_only:
        for doc_id, pdf in pairs:
            r = parse_pdf(pdf, PARSED_DIR, document_id=doc_id, force=args.force)
            print(f"[ok] {doc_id} pages={r.page_count} -> {r.layout_json_path}")
    else:
        results = ingest_and_parse(
            pairs,
            parsed_dir=PARSED_DIR,
            force=args.force,
            overwrite_blob=args.overwrite_blob,
        )
        for r in results:
            print(f"[ok] {r.document_id} pages={r.page_count} blob={r.blob_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
