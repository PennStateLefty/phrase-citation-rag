"""Layout X vs Layout Y retrieval probe.

Runs a fixed set of probe queries against both indices:

* Layout X: hybrid + semantic against ``tax-chunks`` (chunk vector),
  then each retrieved chunk's nested sentences are the citation pool.
* Layout Y: hybrid + semantic against ``tax-sentences`` (per-sentence
  vector), each hit is a direct citation candidate.

Emits a JSON dump and a short per-query summary. This is a *qualitative*
probe — formal GT recall@k waits on the synth-GT generator.

Usage:
    python scripts/compare_layouts.py \
        [--queries probes.json] [--top-k 10] [--out results.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.search.documents import SearchClient  # noqa: E402
from azure.search.documents.models import VectorizedQuery  # noqa: E402

from sentcite.config import AzureConfig  # noqa: E402
from sentcite.indexing import embed_texts  # noqa: E402


DEFAULT_PROBES = [
    "What records must a small business keep for tax purposes?",
    "How long should I keep supporting documents for my tax return?",
    "What depreciation method applies to residential rental property?",
    "When is Section 179 expensing not allowed?",
    "What is the standard mileage rate for business use of a car?",
    "Who qualifies as a statutory employee?",
    "What expenses can a self-employed person deduct for a home office?",
    "How is a partnership's income allocated to partners?",
    "What is the difference between a sole proprietorship and an LLC for tax purposes?",
    "When must an employer file Form 941?",
]


def _cred():
    return DefaultAzureCredential()


def query_chunks(cfg: AzureConfig, q: str, vec: list[float], top_k: int) -> dict:
    sc = SearchClient(cfg.search_endpoint, cfg.search_index_chunks, _cred())
    t0 = time.perf_counter()
    results = list(
        sc.search(
            search_text=q,
            vector_queries=[VectorizedQuery(vector=vec, k_nearest_neighbors=top_k, fields="chunk_vector")],
            query_type="semantic",
            semantic_configuration_name="default",
            top=top_k,
            select=["chunk_id", "document_id", "page", "section_path", "text", "sentences"],
        )
    )
    dt = (time.perf_counter() - t0) * 1000
    hits = []
    candidate_sentences = 0
    for d in results:
        sents = d.get("sentences") or []
        candidate_sentences += len(sents)
        hits.append({
            "chunk_id": d["chunk_id"],
            "document_id": d["document_id"],
            "page": d["page"],
            "section_path": list(d.get("section_path") or []),
            "score": d.get("@search.score"),
            "reranker": d.get("@search.reranker_score"),
            "sentence_count": len(sents),
            "preview": (d.get("text") or "")[:160],
        })
    return {"latency_ms": dt, "hits": hits, "candidate_sentences": candidate_sentences}


def query_sentences(cfg: AzureConfig, q: str, vec: list[float], top_k: int) -> dict:
    sc = SearchClient(cfg.search_endpoint, cfg.search_index_sentences, _cred())
    t0 = time.perf_counter()
    results = list(
        sc.search(
            search_text=q,
            vector_queries=[VectorizedQuery(vector=vec, k_nearest_neighbors=top_k, fields="sentence_vector")],
            query_type="semantic",
            semantic_configuration_name="default",
            top=top_k,
            select=["sentence_id", "chunk_id", "document_id", "page", "section_path", "text"],
        )
    )
    dt = (time.perf_counter() - t0) * 1000
    hits = []
    parents = set()
    for d in results:
        parents.add(d["chunk_id"])
        hits.append({
            "sentence_id": d["sentence_id"],
            "chunk_id": d["chunk_id"],
            "document_id": d["document_id"],
            "page": d["page"],
            "section_path": list(d.get("section_path") or []),
            "score": d.get("@search.score"),
            "reranker": d.get("@search.reranker_score"),
            "text": (d.get("text") or "")[:200],
        })
    return {"latency_ms": dt, "hits": hits, "unique_parent_chunks": len(parents)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queries", type=Path)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "index_projections_eval_results.json",
    )
    args = p.parse_args()

    cfg = AzureConfig.from_env()
    if args.queries:
        probes = json.loads(args.queries.read_text())
    else:
        probes = DEFAULT_PROBES

    report = {
        "top_k": args.top_k,
        "queries": [],
        "summary": {},
    }
    x_lat: list[float] = []
    y_lat: list[float] = []
    overlap_any: list[float] = []

    for q in probes:
        vec = embed_texts([q], cfg=cfg)[0]
        x = query_chunks(cfg, q, vec, args.top_k)
        y = query_sentences(cfg, q, vec, args.top_k)
        # How often did Layout Y find a sentence whose parent chunk was
        # also retrieved by Layout X? Useful agreement signal.
        x_chunks = {h["chunk_id"] for h in x["hits"]}
        y_parents = {h["chunk_id"] for h in y["hits"]}
        inter = x_chunks & y_parents
        agreement = len(inter) / max(1, len(y_parents))
        overlap_any.append(agreement)

        x_lat.append(x["latency_ms"])
        y_lat.append(y["latency_ms"])
        report["queries"].append({
            "query": q,
            "layout_x": x,
            "layout_y": y,
            "y_parent_chunks_also_in_x": sorted(inter),
            "parent_agreement": agreement,
        })

        top_x = x["hits"][0] if x["hits"] else None
        top_y = y["hits"][0] if y["hits"] else None
        print(f"\nQ: {q}")
        if top_x:
            print(f"  X top: {top_x['chunk_id']} p{top_x['page']} rr={top_x['reranker']:.2f}")
            print(f"         {top_x['section_path']}")
        if top_y:
            print(f"  Y top: {top_y['sentence_id']} p{top_y['page']} rr={top_y['reranker']:.2f}")
            print(f"         {top_y['text'][:140]}...")
        print(f"  parent-chunk agreement: {agreement:.2f}  "
              f"X lat={x['latency_ms']:.0f}ms  Y lat={y['latency_ms']:.0f}ms")

    report["summary"] = {
        "queries": len(probes),
        "x_latency_ms_median": statistics.median(x_lat),
        "y_latency_ms_median": statistics.median(y_lat),
        "x_latency_ms_max": max(x_lat),
        "y_latency_ms_max": max(y_lat),
        "parent_agreement_mean": statistics.mean(overlap_any),
        "parent_agreement_min": min(overlap_any),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"\n[done] wrote {args.out}")
    print(f"  median latency  X={report['summary']['x_latency_ms_median']:.0f}ms  "
          f"Y={report['summary']['y_latency_ms_median']:.0f}ms")
    print(f"  parent-chunk agreement mean={report['summary']['parent_agreement_mean']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
