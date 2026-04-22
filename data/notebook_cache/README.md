# Notebook Cache Bundle

A small, committed slice of pipeline artifacts so the walkthrough notebooks
(and their `RESUME_FROM_CACHE` cells) and zero-Azure demos work on a fresh
clone — no Azure credentials, no re-ingestion required.

> ⚠️ **This is a tiny demo slice — not a representative benchmark.**
> Metrics here are illustrative only. For real evaluation, regenerate against
> the full corpus following the main project README.

## Layout

```
data/notebook_cache/
├── parsed/irs_pub_583/             # Document Intelligence output (1 doc)
│   ├── document.md
│   ├── layout.json
│   └── meta.json
├── chunks/irs_pub_583.jsonl        # Chunked sentences/chunks for that doc
├── retrieval/snapshot.json         # One live retrieve() result (dual mode)
├── synth_gt/
│   ├── items.jsonl                 # 5 synthetic QA items (subset of phase1a-100)
│   └── manifest.json
├── eval/
│   ├── items.jsonl                 # 10 per-strategy eval rows (5 q × 2 strategies)
│   ├── manifest.json
│   └── summary.md
├── benchmarks/hagrid_fixture.jsonl # Tiny HAGRID-shape fixture (3 items)
└── README.md                       # (this file)
```

Total size: ~5 MB. Everything is JSONL / JSON / Markdown so git diffs are
meaningful.

## What each file is and where it came from

### `parsed/irs_pub_583/`
**IRS Publication 583 — "Starting a Business and Keeping Records"**, the
smallest document in the corpus (28 pages, ~4 MB parsed).

Produced by:
```bash
python -m sentcite.ingest parse --document-id irs_pub_583
# (writes data/parsed/irs_pub_583/{document.md, layout.json, meta.json})
```
Copied verbatim from `data/parsed/irs_pub_583/`.

### `chunks/irs_pub_583.jsonl`
Chunk + sentence output for Pub 583.

Produced by:
```bash
python -m sentcite.chunking run --document-id irs_pub_583
# (writes data/chunks/irs_pub_583.jsonl)
```
Copied verbatim from `data/chunks/irs_pub_583.jsonl`.

### `retrieval/snapshot.json`
One serialized `RetrievalResult` (see `src/sentcite/retrieval.py`) for a
single demo query taken from `synth_gt/items.jsonl`
(question `synth-0003-irs_pub_583-c0010`):

> *"What type of payment must be reported as income if received by a
> dependent care provider?"*

Produced live (against Azure AI Search + Azure OpenAI embeddings) via:
```python
from sentcite.retrieval import retrieve
res = retrieve(query, mode="dual", k_chunks=5, k_sentences=20)
# json.dumps(dataclasses.asdict(res), indent=2, default=str)
```
The top-level key `_meta.source == "live"` flags that this is a real
Azure round-trip (no fallback was needed). Shape matches
`RetrievalResult` → `{query, mode, chunks[], sentence_candidates[],
latency_ms, chunk_search_hits, sentence_search_hits,
parent_chunks_added}`.

### `synth_gt/items.jsonl`
Five synthetic question/answer ground-truth items — the exact subset of
`data/ground_truth/synthetic/phase1a-100/items.jsonl` that the bundled
`eval/` run was scored against (`question_id` ∈ {`synth-0000-irs_pub_587-c0108`,
`synth-0001-irs_pub_463-c0027`, `synth-0002-irs_pub_17-c0311`,
`synth-0003-irs_pub_583-c0010`, `synth-0005-irs_pub_544-c0124`}).

Regenerate the parent run with:
```bash
python -m sentcite.synth_gt generate --run-id phase1a-100 \
    --target-easy 34 --target-medium 33 --target-hard 33 --seed 7
```
Items reference documents beyond Pub 583 (587, 463, 17, 544). For the
notebooks, you can still *inspect* those items — but to actually *score*
against them, you need the chunks/indexes for those docs too. For a pure
single-doc demo, use the one item whose `document_id == irs_pub_583`.

### `eval/`
Output of the `smoke-eval` run (10 rows = 5 questions × 2 citation
strategies: `inline_prompted`, `post_gen_alignment`).

Produced by:
```bash
python -m sentcite.eval run --run-id smoke-eval \
    --gt-items data/ground_truth/synthetic/phase1a-100/items.jsonl \
    --n 5 --retrieval-mode dual --k-sentences 20 --k-chunks 5 --tau 0.75
```
Copied verbatim from `data/eval/smoke-eval/`. See `summary.md` for the
human-readable report and `manifest.json` for the strategy-level macro
metrics.

### `benchmarks/hagrid_fixture.jsonl`
Three hand-crafted items in the HAGRID JSONL shape understood by
`sentcite.benchmarks.load_hagrid_jsonl`. Shape per record:
```json
{
  "query_id": "...",
  "query": "...",
  "quotes":  [{"idx": "q0", "text": "..."}, ...],
  "answers": [{"answer": "...", "attributable": ["q0", ...]}]
}
```
Alternate attribution keys supported by the loader (`supporting_quotes`,
nested `sentences[].attributable_quotes`, etc.) are exercised by the
unit tests in `tests/test_benchmarks.py`. This fixture is deliberately
tiny and generic (Mona Lisa, Eiffel Tower, speed of light) so it can be
used in zero-Azure notebook demos of the benchmark loader and
`BenchmarkItem → RetrievalResult` adapter.

## Regenerating the whole bundle

```bash
# 0. Activate venv and ensure .env is populated for Azure-backed steps
source .venv/bin/activate

# 1. Parsed + chunks (requires Azure Document Intelligence)
python -m sentcite.ingest parse   --document-id irs_pub_583
python -m sentcite.chunking run   --document-id irs_pub_583
cp -r data/parsed/irs_pub_583  data/notebook_cache/parsed/
cp data/chunks/irs_pub_583.jsonl data/notebook_cache/chunks/

# 2. Synth GT slice (requires Azure OpenAI for authoring)
python -m sentcite.synth_gt generate --run-id phase1a-100 \
    --target-easy 34 --target-medium 33 --target-hard 33 --seed 7
# then filter to the 5 ids referenced by the eval run (see scripts/ if provided)

# 3. Eval run (requires Azure OpenAI for RAG + judge)
python -m sentcite.eval run --run-id smoke-eval \
    --gt-items data/ground_truth/synthetic/phase1a-100/items.jsonl \
    --n 5 --retrieval-mode dual --k-sentences 20 --k-chunks 5 --tau 0.75
cp data/eval/smoke-eval/{items.jsonl,manifest.json,summary.md} data/notebook_cache/eval/

# 4. Retrieval snapshot (requires Azure AI Search + Azure OpenAI embeddings)
python - <<'PY'
import json, dataclasses
from sentcite.retrieval import retrieve
res = retrieve(
    "What type of payment must be reported as income if received by a dependent care provider?",
    mode="dual", k_chunks=5, k_sentences=20,
)
with open("data/notebook_cache/retrieval/snapshot.json", "w") as f:
    json.dump(dataclasses.asdict(res), f, indent=2, default=str)
PY

# 5. HAGRID fixture — edit data/notebook_cache/benchmarks/hagrid_fixture.jsonl by hand.
```

## Fallback notes

No fallback was needed when this bundle was built — the live retrieval
call against Azure AI Search + Azure OpenAI embeddings succeeded (see
`retrieval/snapshot.json` → `_meta.source == "live"`). If you are
regenerating without Azure access, hand-craft a `snapshot.json` whose
top-level keys match the `RetrievalResult` dataclass in
`src/sentcite/retrieval.py` and set `_meta.source = "mock"` so
downstream notebooks can warn the reader.
