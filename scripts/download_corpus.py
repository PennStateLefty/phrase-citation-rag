"""Download the Phase 1 default corpus of public IRS publications.

Run inside the venv:

    source .venv/bin/activate
    python scripts/download_corpus.py                 # download all
    python scripts/download_corpus.py --check         # HEAD each URL, no write
    python scripts/download_corpus.py --only p17      # download a subset

All files are written to data/raw_pdfs/. The MANIFEST.md in that folder
is the human-readable index; this script's CORPUS list is the source of
truth.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST = REPO_ROOT / "data" / "raw_pdfs"


@dataclass(frozen=True)
class Doc:
    document_id: str   # stable identifier used as the document_id in schema.py
    filename: str
    url: str
    title: str
    rationale: str


# Phase 1 default corpus — business-expense deductibility, meals/entertainment,
# substantiation, depreciation, fringe benefits, and small-business tax guides.
# All stable IRS.gov publication URLs. The Tax SME can edit/extend this list.
CORPUS: list[Doc] = [
    Doc(
        "irs_pub_17",
        "p17.pdf",
        "https://www.irs.gov/pub/irs-pdf/p17.pdf",
        "Your Federal Income Tax (For Individuals)",
        "Comprehensive individual tax reference; common starting point for audit questions.",
    ),
    Doc(
        "irs_pub_334",
        "p334.pdf",
        "https://www.irs.gov/pub/irs-pdf/p334.pdf",
        "Tax Guide for Small Business",
        "Core small-business expense deductibility guidance; successor context for retired Pub 535.",
    ),
    Doc(
        "irs_pub_463",
        "p463.pdf",
        "https://www.irs.gov/pub/irs-pdf/p463.pdf",
        "Travel, Gift, and Car Expenses",
        "Primary IRS text on IRC § 274 meals / entertainment / travel substantiation rules.",
    ),
    Doc(
        "irs_pub_946",
        "p946.pdf",
        "https://www.irs.gov/pub/irs-pdf/p946.pdf",
        "How To Depreciate Property",
        "Depreciation and § 179 — frequent source of audit disputes.",
    ),
    Doc(
        "irs_pub_15b",
        "p15b.pdf",
        "https://www.irs.gov/pub/irs-pdf/p15b.pdf",
        "Employer's Tax Guide to Fringe Benefits",
        "Authoritative on taxable vs. excludable fringe benefits (meals on premises, de minimis, etc.).",
    ),
    Doc(
        "irs_pub_587",
        "p587.pdf",
        "https://www.irs.gov/pub/irs-pdf/p587.pdf",
        "Business Use of Your Home",
        "Home-office deduction tests; common audit question type.",
    ),
    Doc(
        "irs_pub_541",
        "p541.pdf",
        "https://www.irs.gov/pub/irs-pdf/p541.pdf",
        "Partnerships",
        "Entity-level deductibility issues that cross-reference §§ 162 / 274.",
    ),
    Doc(
        "irs_pub_542",
        "p542.pdf",
        "https://www.irs.gov/pub/irs-pdf/p542.pdf",
        "Corporations",
        "Corporate-level deductibility; useful for multi-document reasoning questions.",
    ),
    Doc(
        "irs_pub_544",
        "p544.pdf",
        "https://www.irs.gov/pub/irs-pdf/p544.pdf",
        "Sales and Other Dispositions of Assets",
        "Asset basis and disposition rules that interact with depreciation questions.",
    ),
    Doc(
        "irs_pub_583",
        "p583.pdf",
        "https://www.irs.gov/pub/irs-pdf/p583.pdf",
        "Starting a Business and Keeping Records",
        "Recordkeeping / substantiation guidance — directly relevant to auditor workflows.",
    ),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _head(url: str) -> tuple[int, int | None]:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        size = resp.headers.get("Content-Length")
        return resp.status, int(size) if size else None


def _download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "sentcite-corpus/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:  # noqa: S310
        total = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
        return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="HEAD each URL only; do not write files.")
    parser.add_argument("--only", action="append", default=[], help="Limit to these document_ids (repeatable).")
    parser.add_argument("--force", action="store_true", help="Re-download even if the file already exists.")
    args = parser.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    selected = [d for d in CORPUS if not args.only or d.document_id in args.only]
    if not selected:
        print(f"No matching documents for --only={args.only}", file=sys.stderr)
        return 2

    failures = 0
    for doc in selected:
        target = DEST / doc.filename
        if args.check:
            try:
                status, size = _head(doc.url)
                size_s = f"{size:>12,}" if size else "unknown"
                print(f"[HEAD {status}] {size_s} bytes  {doc.document_id}  {doc.url}")
            except Exception as e:  # noqa: BLE001
                print(f"[FAIL] {doc.document_id}  {doc.url}  {e}", file=sys.stderr)
                failures += 1
            continue

        if target.exists() and not args.force:
            print(f"[skip] {doc.document_id} already present at {target.relative_to(REPO_ROOT)}")
            continue

        try:
            n = _download(doc.url, target)
            print(f"[ok]   {doc.document_id} {n:>12,} bytes  sha256={_sha256(target)[:12]}…")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {doc.document_id}  {doc.url}  {e}", file=sys.stderr)
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
