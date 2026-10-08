# Phase 2 Methodology: Letta-First Black-Box Reflection and Compression Probes

## Objective

Phase 2 first tests the active Letta framework condition. It evaluates whether
Letta exposes an observable trigger for reflection or compression as controlled
memory volume increases. Historical Mem0 results are retained as methodology
evidence, but are out of scope for the active experiment. The goal is to estimate a threshold only
when the evidence supports one; otherwise the result is reported as
unobservable or not observed.

## Experimental contract

All Letta probes call only the framework-neutral `MemoryAdapter` methods:

- `write(text, session_id)` for controlled input;
- `stats()` for observable state;
- no Mem0 internals, private fields, database inspection, or provider-specific
  APIs.

This preserves portability and prevents implementation knowledge from leaking
into the attack workload.

## Controlled procedure

1. Create a fresh collection/session for every trial.
2. Capture the initial `stats()` snapshot.
3. Write unique, synthetic facts in fixed-size batches.
4. Capture `stats()` after every batch and record write latency.
5. Repeat with different batch sizes and text lengths when resources permit.
6. Run at least three independent trials for any claimed threshold.
7. Preserve the complete JSON result, environment metadata, model identity,
   adapter configuration, and failed/aborted trials.

The implementation is in `mabench/attacks/threshold_probe.py`:
`probe_compression_threshold` uses entry-count contraction, while
`probe_reflection_trigger` uses a change in `last_reflection_ts`.

The runner is `scripts/phase2_probes.py`; Letta is selected with
`--framework letta`. A resource-conscious Letta smoke run is:

```powershell
python scripts/phase2_probes.py --framework letta --step 10 --max-writes 10 --max-batches 1
```

For the paper baseline, run three fresh Letta trials with 10-write batches and
50 maximum writes. Use a fresh `--session-id` and output file for every trial;
Letta does not use `--local-chroma`. Store artifacts under
`results/Phase2/Letta/` and summarize them in a Phase 2 results document.

## Operational definitions

| Event | Operational evidence | Interpretation |
|---|---|---|
| Compression observed | `entry_count` decreases between adjacent batches | A threshold candidate exists at the first batch endpoint |
| Reflection observed | `last_reflection_ts` changes | A threshold candidate exists at the first changed timestamp |
| Not observed | Signal is available and unchanged through the probe | No trigger was observed within tested range |
| Unavailable | Adapter returns no signal | Cannot make a trigger claim |

An entry-count decrease is not automatically attributed to compression: it may
also represent deduplication, replacement, deletion, or extraction behavior.
Therefore the paper must call this an *observable contraction* unless a
framework-specific audit trail confirms compression.

## Required methodology records

For each run, record:

- run ID, date/time, session and collection IDs;
- number of writes, batch size, topic count, and text-length condition;
- model name, digest, quantization, intrinsic context length, and active
  runtime context length;
- embedding model and vector-store mode;
- every observation, including null/unavailable fields;
- write latency per batch and total elapsed time;
- threshold estimate or explicit non-detection status;
- failed trials, retries, OOM events, and environmental interruptions.

## Required analyses and safeguards

- Report threshold estimates as a range between the last negative and first
  positive observation; do not report a single exact trigger without a binary
  refinement using fresh sessions.
- Report trial-to-trial variability with mean, standard deviation, minimum, and
  maximum when three or more trials complete.
- Test false positives by repeating the same write pattern in fresh sessions.
- Test false negatives by varying semantic similarity and text length while
  holding write count fixed.
- Keep raw observations immutable and place derived summaries in a separate
  table or document.
- Do not treat unchanged result count as proof that no internal reflection or
  compression occurred.

## Current implementation limitation

The Letta adapter exposes passage entry counts but reports reflection and
compression timestamps as unavailable. Therefore, Letta compression evidence
can only be an observable entry-count contraction, while reflection is expected
to remain unavailable unless a public adapter signal changes. Neither result
proves that an internal subsystem did or did not execute. The first Phase 2
result is therefore an observability assessment. Historical Mem0 results are
not included in the Letta aggregate baseline.

Each probe now uses an independent adapter instance and session so that the
reflection and compression observations cannot contaminate one another through
adapter-level aggregate statistics. A probe whose relevant signal is absent is
reported with status `unavailable`, distinct from `not_observed`.

## Paper-ready reporting template

> We performed black-box threshold probes using fresh sessions and fixed-size
> batches. Each probe used only the adapter's public write and statistics
> contract. A trigger was accepted only when an observable state signal changed;
> unavailable signals were not treated as negative evidence. We report the
> last negative and first positive batch, repeated-trial variability, and all
> resource or observability limitations.
