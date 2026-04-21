# Corpus Manifest

**Phase 1 default corpus** — selected by the ML Engineer + PM in lieu of a
Tax SME (see plan Phase 1a). Theme: business-expense deductibility,
meals/entertainment, substantiation, depreciation, fringe benefits, and
small-business tax reference.

The source of truth is the `CORPUS` list in `scripts/download_corpus.py`.
Run `python scripts/download_corpus.py` (inside the venv) to populate
`data/raw_pdfs/`.

| # | document_id | Filename | Title | Rationale |
|---|---|---|---|---|
| 1 | `irs_pub_17`   | p17.pdf   | Your Federal Income Tax (Individuals)     | Comprehensive individual reference. |
| 2 | `irs_pub_334`  | p334.pdf  | Tax Guide for Small Business              | Small-biz deductibility (post-Pub 535). |
| 3 | `irs_pub_463`  | p463.pdf  | Travel, Gift, and Car Expenses            | Primary IRS text on § 274 substantiation. |
| 4 | `irs_pub_946`  | p946.pdf  | How To Depreciate Property                | Depreciation / § 179 audit territory. |
| 5 | `irs_pub_15b`  | p15b.pdf  | Employer's Tax Guide to Fringe Benefits   | Taxable vs. excludable fringe benefits. |
| 6 | `irs_pub_587`  | p587.pdf  | Business Use of Your Home                 | Home-office deduction tests. |
| 7 | `irs_pub_541`  | p541.pdf  | Partnerships                              | Entity-level deductibility crossrefs. |
| 8 | `irs_pub_542`  | p542.pdf  | Corporations                              | Multi-document reasoning fodder. |
| 9 | `irs_pub_544`  | p544.pdf  | Sales and Other Dispositions of Assets    | Basis + disposition, interacts w/ depreciation. |
| 10| `irs_pub_583`  | p583.pdf  | Starting a Business and Keeping Records   | Recordkeeping / substantiation. |

**Source:** all from `https://www.irs.gov/pub/irs-pdf/` (stable URL
pattern maintained by IRS). These are public-domain US Government works.

**SME override:** this list is a placeholder chosen to unblock Phase 1a.
When a Tax SME is engaged (Phase 1b, H1), they should edit `CORPUS` in
`download_corpus.py` and re-run the downloader.
