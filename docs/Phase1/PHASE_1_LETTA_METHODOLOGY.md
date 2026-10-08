# Phase 1 Letta Baseline Methodology

This is the active Phase 1 methodology for the Letta-only implementation.
Historical Mem0 results remain under their original artifacts for provenance
but are excluded from active aggregates.

## Target

- Letta OSS server `0.16.8`, pinned in `docker-compose.letta.yml`.
- Python SDK `letta-client==1.12.1`.
- Ollama model configured through `LETTA_MODEL`.
- Local embeddings are served by `scripts/local_model_proxy.py`, using the
  cached `BAAI/bge-small-en-v1.5` model and an OpenAI-compatible endpoint.
  Ollama remains the local generation backend.
- Letta agent context limit: 2,048 tokens by default, matching the constrained
  local runtime used during the Mem0 experiments.
- Sleep-time memory management enabled.
- Sliding-window conversation compaction enabled.

## Archived Llama 3.1 trial

The first Letta configuration used the following model before the constrained
hardware track was switched to a smaller model:

| Field | Recorded value |
|---|---|
| Ollama tag | `llama3.1:8b` |
| Parameters | 8.0B |
| Quantization | Q4_K_M |
| Ollama model size | 4,920,753,328 bytes (approximately 4.9 GB) |
| Intrinsic context length | 131,072 tokens |
| Active requested context | 2,048 tokens |
| Recorded digest | `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` |
| Trial outcome | Incomplete; Ollama reported insufficient system memory |

The Llama trial is retained as a failed hardware-compatibility condition, not
as a completed Phase 1 result. It required approximately 1.3--2.1 GiB during
generation while the runtime reported only approximately 1.3--1.5 GiB
available. The model may therefore be removed from the local Ollama cache to
recover disk space; the tag, digest, size, and failure status above preserve its
experimental identity.

## Resource-constrained local serving

The host has 8 GB RAM. To avoid loading a second multi-billion-parameter
model, the embedding service reuses the already cached 133 MB
`BAAI/bge-small-en-v1.5` model in the project `.venv`. The proxy forwards
  generation requests to Ollama and exposes only the embedding endpoint needed by
Letta. The Letta Docker database uses a separate proxy-specific volume so stale
provider endpoints from the failed Ollama-only trials are not reused.
The proxy forces Ollama `num_ctx=2048` to prevent the 8 GB host from allocating
the model's advertised 131k context window.

## Procedure

Run the same clean fixture and 15 retrieval/answer queries used for Mem0. Each
repeat uses a fresh Letta agent/session and writes to:

```text
results/Phase1/Letta/
```

The benchmark records retrieval quality, answer correctness, write/query/
answer latency, entry count, model configuration, and service identity.

## Comparability rule

The fixtures and scoring code are held constant. Framework-specific behavior is
not normalized away: Letta's archival passage IDs, context compaction, and
sleep-time activity are recorded as part of the target condition. Mem0 and
Letta metrics must be compared only after confirming model, embedding, context
limit, repeat count, and fixture version.

## Required evidence

For each run preserve the manifest, SQLite event database, service version,
model handle, embedding handle, context limit, compaction mode, sleep-time
setting, Docker image digests, and any failed/OOM/timeout trial. Do not combine
Letta and Mem0 rows in one aggregate baseline.

## Invalid initial Qwen run and parser correction (2026-08-27)

The first completed Qwen 1.5B run (`20260827T120143Z_66a0dae3`) is retained
under `results/Phase1/Letta/20260827T120143Z_66a0dae3/`, but is excluded from
the valid baseline aggregate. Its manifest is valid; however, all retrieval
and answer metrics were zero because the adapter read Letta search results
from a `text` field while Letta's search `Result` schema returns the passage
under `content`. Consequently, the generated answer context was empty. The
adapter was corrected to accept both `content` and `text`, and to count Letta's
list-valued passage response correctly. A second related defect was found in
the same audit: Letta's passage-create response is a list, so the adapter had
recorded null passage IDs; this was corrected by normalizing the first created
passage before mapping fixture IDs. This run is a preserved diagnostic
artifact, not evidence of Qwen or Letta quality.

The subsequent run (`20260827T121015Z_bd843875`, database
`results/Phase1/Letta/phase1_qwen25_r2.sqlite3`) is also excluded from the
retrieval baseline. It produced 15/15 correct answers, but its write events
still contained null memory IDs because it was executed before the list-response
correction. Its answer score may be reported only as a diagnostic observation.

## Paper wording

## Valid Qwen Letta baseline (2026-08-27)

Run identity:

- Run ID: `20260827T121405Z_5301afe4`
- Manifest: `results/Phase1/Letta/20260827T121405Z_5301afe4/manifest.json`
- SQLite database: `results/Phase1/Letta/phase1_qwen25_r3.sqlite3`
- Model: `ollama/qwen2.5:1.5b-instruct`
- Embeddings: `ollama/nomic-embed-text:latest`
- Context limit: 2,048 tokens
- Repeats: 1; queries: 15; writes: 20

Aggregate metrics for this single repeat:

| Metric | Result |
|---|---:|
| Recall@5 | 1.0000 |
| Recall@10 | 1.0000 |
| Precision@5 | 0.2000 |
| Precision@10 | 0.1000 |
| MRR | 0.9333 |
| nDCG | 0.9508 |
| Answer correctness | 14/15 (0.9333) |

The only answer failure was `q12`; its retrieval metrics were nevertheless
perfect. Because this is one repeat, these values are a preliminary baseline,
not a generalization claim. The r3 run is the first valid Letta retrieval run
and should be used for framework-condition comparisons.

> We evaluated Letta as a separate memory-framework condition using the same
> clean workload and scoring protocol as the Mem0 control. Letta was configured
> with an explicit context limit, sliding-window compaction, and sleep-time
> memory management. Results were stored separately because framework-managed
> memory state and event semantics are not directly interchangeable.
