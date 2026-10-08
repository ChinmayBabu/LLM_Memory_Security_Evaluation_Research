# Archived Phase 1 Mem0 Methodology: Adapter and Clean Baseline

This document preserves the original Mem0 findings for research provenance.
Mem0 is no longer an active dependency or experiment condition; the active
implementation uses Letta and is documented separately in
`PHASE_1_LETTA_METHODOLOGY.md`.

## Purpose

Phase 1 establishes a reproducible clean baseline for the Mem0 memory system.
No attack traffic, threshold probing, mitigation, or adversarial filler is used
in this phase. The baseline is the control condition against which every later
attack and recovery result will be compared.

The implementation must access Mem0 through the framework-neutral
`MemoryAdapter` interface. Attack and metric code must not call Mem0-specific
methods directly.

## Fixed system configuration

The following configuration is the initial MVP configuration and must be stored
in every run manifest:

| Component | Required value to record |
|---|---|
| Python | Version and architecture; primary environment is Python 3.11.x |
| Mem0 | Exact package version |
| Vector database | Chroma version, image tag, endpoint, and persistence mode |
| LLM | Exact Ollama model tag, digest, parameter count, quantization, and context length |
| Embeddings | Exact sentence-transformer model identifier and revision |
| Operating system | Windows version and architecture |
| Hardware | CPU, physical cores, RAM, GPU, VRAM, and driver version if applicable |
| Runtime | Docker, Docker Compose, Ollama, and CUDA/ROCm versions where applicable |
| Configuration | Full sanitized Mem0, Chroma, Ollama, and benchmark configuration |
| Randomness | Global seed and any library-specific seeds |
| Repository | Git commit when available; otherwise record that the workspace is uncommitted |

The current primary LLM is `llama3.1:8b`. The model output shown by Ollama
must be recorded as evidence: 8.0B parameters, Q4_K_M quantization, and the
reported context length. A different model is a separate experimental track,
not a silent replacement.

## Adapter contract

Implement `mabench/adapters/base.py` with these public operations:

```python
class MemoryAdapter(ABC):
    def write(self, text: str, session_id: str) -> dict: ...
    def query(self, prompt: str, session_id: str, k: int = 5) -> list: ...
    def stats(self) -> dict: ...
    def force_reflect(self): ...
    def force_compress(self): ...
    def answer(self, prompt: str, session_id: str) -> str: ...
```

Required behavior:

- `write()` persists one conversational memory and returns normalized metadata,
  including any framework memory ID when available.
- `query()` returns a normalized list while preserving framework IDs, text,
  scores, and raw metadata where available.
- `stats()` always returns `entry_count` and `storage_bytes` when measurable,
  plus nullable reflection/compression timestamps.
- Unsupported `force_reflect()` and `force_compress()` operations raise
  `NotImplementedError`; they must not be silently simulated.
- `answer()` performs retrieval and generation using the configured LLM and
  returns the generated answer without modifying evaluation inputs.
- Session IDs are explicit and never generated implicitly inside attack or
  evaluation code.

## Clean baseline workload

Use a fixed, deterministic workload before introducing LongMemEval or LoCoMo.
This catches integration errors without making dataset quality a confounding
factor.

Each baseline run must:

1. Start from a fresh Chroma/Mem0 store.
2. Create one unique session ID.
3. Perform a documented warm-up sequence.
4. Write a fixed set of factual memories covering at least five topics.
5. Query each topic using paraphrased questions.
6. Generate answers for the same questions.
7. Collect system state and resource metrics for every operation.
8. Mark warm-up events separately from measured events.
9. Close the run with a success or failure status.

The fixed fixture should contain:

- At least 20 writes for normal baseline behavior.
- At least 10 retrieval queries.
- Distinct gold memory IDs for each query where the adapter exposes IDs.
- Questions that require direct retrieval rather than outside factual knowledge.
- A small number of negative queries with no matching memory.

The fixture text, ordering, session ID policy, and seed must be checked into
the repository so every baseline run uses identical inputs.

## Measurements required per event

Every write, query, answer, and state snapshot must be logged to SQLite with a
monotonic timestamp and event index.

### Performance and resource metrics

- Operation type.
- Wall-clock latency in milliseconds.
- CPU utilization percentage.
- Process RSS in MB.
- Optional process CPU time.
- Attacker tokens are not applicable in Phase 1 and must remain null.
- LLM input and output token counts when exposed by Ollama.
- Error type and message for failed operations.

### Memory-state metrics

- Entry count.
- Storage bytes and how they were measured.
- Number of returned results.
- Reflection timestamp, event, or observation status.
- Compression timestamp, event, or observation status.
- Framework memory IDs.
- Vector-store collection or namespace identifier.

### Retrieval and answer metrics

- Query text hash; do not log sensitive raw data by default.
- Retrieved memory IDs and normalized similarity scores.
- Recall@1, Recall@5, and Recall@10 when gold IDs exist.
- Precision@5 and Precision@10.
- MRR and nDCG.
- Answer correctness and the evaluation rubric used.
- Raw answer text only in a separately controlled research artifact if privacy
  and dataset licensing permit it.

For the controlled Phase 1 fixture, answer correctness is deterministic: each
query declares required answer terms, and `answer_correct=1` only when every
required term occurs in the normalized answer. This avoids introducing a
second language model as an unmeasured judge. Public-dataset evaluation may use
a separately documented rubric after the adapter baseline is stable.

### Metadata and scoring preservation record

The raw SQLite event database is the authoritative execution artifact and must
not be overwritten when a measurement or scoring bug is discovered. Corrections
are recorded as derived analyses with the raw value, correction rule, and reason
for the change.

For the initial five-repeat baseline:

- Raw `q09` answer scores are `0` because the model returned `5` and the first
  scorer required the word `five`.
- The corrected scorer normalizes number words to digits, so `5` and `five` are
  equivalent; corrected answer correctness is `1.0000`.
- The raw database remains unchanged; the corrected value is a derived metric.
- The model's intrinsic context length is `131072`, while the active runtime
  context was constrained to `2048` to fit available memory. Both values must
  be reported separately.
- The final manifests were created before automatic Ollama digest capture was
  added. The setup evidence records digest
  `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` and model
  size `4920753328` bytes; future runs must capture these fields automatically.

## Reflection and compression observability

Mem0 may not expose reflection and compression as first-class public events.
The adapter must classify each signal as one of:

- `observed`: directly exposed by the framework or database instrumentation;
- `inferred`: derived from state transitions or correlated writes;
- `unavailable`: no defensible signal exists.

The paper must never describe an inferred or unavailable signal as directly
observed. For Phase 1, record the baseline observability classification even if
the result is `unavailable`. This is a validity requirement for the later
threshold-probing contribution.

## Run isolation and reset protocol

Each run must use a fresh database state and unique run ID. The reset protocol
must be deterministic and documented:

- Stop or clear the previous benchmark session.
- Remove only the experiment's Chroma collection or use a fresh isolated store.
- Initialize a new SQLite result database or run namespace.
- Verify entry count is zero before the first measured write.
- Verify the selected model and embedding configuration are unchanged.

No run may reuse memories, collections, or cached evaluation outputs from a
previous run unless that reuse is explicitly part of a later recovery test.

## Replication protocol

The Phase 1 baseline must use at least five independent repeats after the smoke
test passes. Report the smoke test separately; it is not one of the five
research repeats.

For each repeat:

- Use the same fixture and seed policy.
- Use a fresh store.
- Use the same warm-up count.
- Exclude warm-up events from aggregate performance statistics.
- Preserve all event-level rows, including failures and timeouts.

Report mean, median, standard deviation, p95 latency, and confidence intervals
for the primary performance measures. Report per-query and aggregate quality
metrics rather than only a single overall score.

## Required Phase 1 artifacts

Implementation artifacts:

- `mabench/adapters/base.py`
- `mabench/adapters/mem0_adapter.py`
- Clean baseline workload and fixed fixture
- Adapter contract tests
- Mem0/Chroma integration smoke test
- Per-event SQLite logging integration

Research artifacts:

- Environment/run manifest for every run.
- Raw SQLite database.
- Sanitized experiment configuration.
- Baseline summary table.
- Retrieval-quality summary table.
- Latency distribution plot.
- Memory-state growth plot.
- Failure and observability report.

## Paper tables and figures

Phase 1 must provide the data for:

1. **System configuration table:** software versions, models, hardware, and
   database configuration.
2. **Clean performance table:** write, query, and answer latency with mean,
   median, standard deviation, and p95.
3. **Clean memory-quality table:** recall, precision, MRR, nDCG, and answer
   correctness.
4. **Memory-state figure:** entry count and storage bytes over clean writes.
5. **Resource figure:** CPU and RSS distributions during clean traffic.
6. **Observability table:** directly observed, inferred, and unavailable
   reflection/compression signals.

## Acceptance criteria

Phase 1 is complete only when:

- The adapter contract tests pass.
- A fresh Mem0/Chroma store accepts writes and returns searchable memories.
- `answer()` completes using the local Ollama model.
- Every measured operation produces a valid SQLite event row.
- Every run has a unique manifest and configuration snapshot.
- A clean run can be repeated without cross-run contamination.
- The five-repeat baseline produces stable, inspectable aggregates.
- Reflection/compression observability is explicitly classified.
- No attack implementation is required or used in this phase.

## Methodology claims supported by Phase 1

Phase 1 supports only these claims:

- The benchmark provides a framework-neutral adapter boundary.
- The Mem0/Chroma/Ollama configuration is operational and reproducible.
- Clean-system latency, resource, storage, and retrieval-quality baselines were
  measured under a documented workload.
- Later attack impact can be expressed as change from a measured clean control.

Phase 1 does not support claims about attack effectiveness, threshold values,
reflection loops, compression saturation, recovery, or mitigation benefit.
