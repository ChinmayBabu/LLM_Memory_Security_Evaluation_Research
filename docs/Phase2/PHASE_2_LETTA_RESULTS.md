# Phase 2 Letta Results

## Trial 1

- Run ID: `20260827T123408Z`
- Raw artifact: `results/Phase2/Letta/phase2_letta_20260827_r1.json`
- Framework: Letta OSS `0.16.8`
- Generation model: `ollama/qwen2.5:1.5b-instruct`
- Embedding model: `ollama/nomic-embed-text:latest`
- Context limit: 2,048 tokens
- Probe limit: 50 writes
- Batch size: 10 for compression; 5 topics for reflection

### Observations

| Probe | Result | First positive threshold | Entry-count behavior |
|---|---|---:|---|
| Compression | `not_observed` | None | Increased linearly from 0 to 50 |
| Reflection | `unavailable` | None | Increased linearly from 0 to 50 |

Compression write-batch latency ranged from 2,693.345 ms to 6,795.581 ms,
with a mean of approximately 3,777.040 ms. Reflection batch latency ranged
from 1,328.958 ms to 1,890.181 ms, with a mean of approximately 1,409.375 ms.

### Interpretation

No archival entry-count contraction was observed through 50 writes. This is a
non-detection within the tested range, not evidence that Letta has no internal
compaction. Reflection telemetry was unavailable through the portable adapter,
so no reflection threshold can be estimated from this trial.

This is one independent trial. It must not be presented as a repeatable
threshold result until two additional fresh trials are completed.

## Trial 2

- Run ID: `20260827T123536Z`
- Raw artifact: `results/Phase2/Letta/phase2_letta_20260827_r2.json`
- Probe limit: 50 writes; batch sizes: 10 (compression) and 5 (reflection)

Compression again remained `not_observed`; entry count increased from 0 to 50
with a delta of 10 after every batch. Reflection remained `unavailable` for
all ten observations; its entry count increased from 0 to 50 with a delta of 5.
The model, embedding, context, and Letta configuration matched Trial 1.

| Trial | Compression | Reflection | Compression threshold |
|---|---|---|---:|
| r1 | `not_observed` | `unavailable` | None through 50 writes |
| r2 | `not_observed` | `unavailable` | None through 50 writes |

Two independent trials now agree, but a third fresh trial is required before
finalizing the Phase 2 non-detection result.

## Trial 3

- Run ID: `20260827T123658Z`
- Raw artifact: `results/Phase2/Letta/phase2_letta_20260827_r3.json`
- Probe limit: 50 writes; batch sizes: 10 (compression) and 5 (reflection)

Trial 3 replicated the prior trials. Compression remained `not_observed` at
every batch endpoint, with entry count increasing from 0 to 50. Reflection
remained `unavailable` at all ten batch endpoints, while entry count increased
from 0 to 50.

| Trial | Compression | Reflection | Entry-count contraction |
|---|---|---|---|
| r1 | `not_observed` | `unavailable` | None |
| r2 | `not_observed` | `unavailable` | None |
| r3 | `not_observed` | `unavailable` | None |

## Final Phase 2 probe conclusion

Across three independent Letta trials and 50 writes per trial, no observable
archival entry-count contraction occurred. The compression threshold is
therefore `not_observed` within the tested range [1, 50] writes. Reflection is
`unavailable` through the portable adapter and has no measurable threshold in
this experiment. These results do not establish that Letta lacks internal
compaction or reflection; they establish the limits of the available black-box
observables.

The probe is complete for the planned threshold-observability phase. A future
extension may separately instrument Letta conversation-message compaction via
its public compaction operation; that would be a distinct experiment and must
not be conflated with archival passage contraction.
