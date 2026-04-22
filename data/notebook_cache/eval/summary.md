# Phase 1a evaluation — smoke-eval

- RAG: `gpt-4.1-1`
- Synth-GT: `mistral-large-3`
- Judge: `llama-3.3-70b-instruct`
- Retrieval: mode=`dual`, k_sentences=20, k_chunks=5, tau=0.75, top_k=3
- Elapsed: 241.0s

## Strategy comparison

| Metric | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| Precision | 0.275 | 0.000 |
| Recall | 0.313 | 0.000 |
| F1 | 0.270 | 0.000 |
| Coverage | 1.000 | 0.440 |
| Retrieval R@k | 0.760 | 0.760 |
| Faithful % | 0.836 | 0.438 |
| Stability | 0.723 | 0.375 |

### F1 by difficulty

| Difficulty | inline_prompted | post_gen_alignment |
| --- | --- | --- |
| easy | 0.229 (n=3) | 0.000 (n=3) |
| medium | 0.333 (n=2) | 0.000 (n=2) |
| hard | n/a | n/a |
