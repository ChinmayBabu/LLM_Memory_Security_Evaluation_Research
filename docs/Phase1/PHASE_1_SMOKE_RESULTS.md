# Archived Phase 1 Mem0 Smoke Results

## Run identity

The corrected smoke run was executed on 2026-08-24:

- Run ID: `20260824T153911Z_8f0623ac`
- Manifest: `results/20260824T153911Z_8f0623ac/manifest.json`
- SQLite database: `results/phase1_smoke_v3.sqlite3`
- System: Mem0 with embedded Chroma
- Workload: 20 deterministic writes, 15 retrieval queries, and 15 answers
- Repeats: 1 smoke repeat
- Model: Llama 3.1 8B, Q4_K_M
- Ollama context limit: 2048 tokens
- Embeddings: `BAAI/bge-small-en-v1.5`, 384 dimensions
- Chroma retrieval: semantic-only; BM25 hybrid search unavailable
- Mem0 spaCy preprocessing: unavailable; semantic-only processing used

## Retrieval results

| Metric | Smoke result |
|---|---:|
| Recall@5 | 1.0000 |
| Recall@10 | 1.0000 |
| Precision@5 | 0.2000 |
| Precision@10 | 0.1000 |
| MRR | 0.8556 |
| nDCG | 0.8929 |

All 15 gold memories were retrieved within the top five results. Precision is
low by construction because each query has one gold memory: one relevant item
in five results gives `1/5 = 0.2`, and one in ten gives `1/10 = 0.1`.

## Answer latency

| Measurement | Result |
|---|---:|
| Answer events | 15/15 |
| Mean latency | 3428 ms |
| Median latency | 2895 ms |
| Approximate p95 latency | 5592 ms |

The smoke run predates deterministic answer-correctness logging, so it must not
be used as the final answer-correctness baseline. A post-fix run is required.

## Interpretation and limitations

This is an integration smoke result, not a paper result. It validates that the
Mem0 adapter, local embedding cache, Chroma persistence, Ollama generation,
SQLite event logger, and retrieval-ID mapping work together.

Do not use it as evidence for attack impact, recovery, threshold behavior, or
cross-framework resilience. The final clean baseline requires five independent
runs using fresh collections, deterministic answer-correctness scoring, and
automatic model metadata capture.
