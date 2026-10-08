# Reflection-Subsystem Security Benchmark and Framework Comparison: Final Report

## Executive summary

This project presents a security benchmark and framework comparison for
attacker-controlled conversation traffic in LLM memory systems. It evaluates
Letta OSS sleeptime reflection and Mem0's synchronous extraction path. The
implementation and bounded experiments are complete. The evidence supports a
qualified conclusion: the architectures expose different memory-processing
surfaces, while the tested setup did not demonstrate a denial of service or a
confirmed memory-poisoning vulnerability.

The final paper should distinguish architecture, observable memory-processing
cost, service availability, and memory integrity. Compression and
reflection-to-compression cascading are excluded from the final study.

A Mem0/Chroma comparative track is now implemented and has fresh clean-baseline
and extraction-cost artifacts. It is not a Letta-equivalent reflection attack:
local Mem0 has no sleeptime reflection subsystem. The archived Mem0 baseline
must not be pooled with the new artifacts or with Letta results.

The first fresh Mem0/Ollama smoke completed using Qwen 2.5 1.5B and Ollama
`nomic-embed-text:latest`. All 20 writes and 15 queries completed; Recall@5
and Recall@10 were 1.0 for every query, with 14/15 deterministic answer checks
passing. Chroma reported semantic-only search and Mem0 reported missing
optional spaCy preprocessing. This validates the comparative adapter and
clean path, not a Mem0 reflection attack.

## Environment

- Letta OSS: `letta/letta:0.16.8`.
- Local Letta API: port `8283`; PostgreSQL/pgvector: port `5432`.
- Qwen 2.5 1.5B through the local MABench proxy on port `8787`.
- Embeddings: `nomic-embed-text:latest`.
- Typical settings: `MABENCH_OLLAMA_CONTEXT=1024`, Letta context limit 2048.
- The Docker healthcheck was corrected from missing `wget` to available `curl`;
  Letta and PostgreSQL were verified healthy.

## Implementation

### Workloads

- `mabench/adapters/letta_adapter.py`: Letta adapter, metadata, sleeptime
  controls, and explicit SDK compatibility fallback.
- `mabench/attacks/reflection_loop.py`: bounded pressure and exact-length clean
  controls.
- `scripts/phase3_5_availability.py`: concurrent legitimate traffic and
  attacker-rate evaluation with preserved failures/timeouts.
- `scripts/phase3_reflection_surface.py`: message-length/topic cost surface.
- `scripts/phase3_reflection_integrity.py`: benign, generalizable,
  non-transferable, and adversarial scenarios.
- `scripts/phase3_integrity_heldout.py`: held-out clean-query validation for
  persistence screening.
- `mabench/adapters/mem0_adapter.py`: isolated Mem0/Chroma adapter with
  session-scoped writes/search and explicit unavailable reflection signals.
- `scripts/phase1_mem0.py`: deterministic Mem0 clean-baseline runner.
- `scripts/mem0_extraction_surface.py`: bounded Mem0 `infer=True` extraction
  cost runner using the shared pressure/clean message generator.
- `scripts/mem0_extraction_sweep.py`: three-repeat matched pressure/control
  extraction matrix runner.
- `scripts/mem0_integrity_comparison.py`: matched Mem0 direct-import versus
  synchronous-extraction integrity runner.
- `scripts/mem0_integrity_matrix.py`: four-scenario repeated Mem0 integrity
  matrix with retention and held-out-query accounting.
- `scripts/mem0_extraction_debug.py`: evaluator-only extraction-response and
  retention diagnostics.
- `scripts/framework_comparison_report.py`: paper-ready comparison export from
  verified Letta and Mem0 artifacts.

### Telemetry

- `scripts/local_model_proxy.py`: foreground/reflection classification,
  correlation headers, token usage, and mitigation outcomes.
- `scripts/direct_reflection_telemetry.py`: Letta logs, explicit server run and
  agent IDs, timestamps, Docker resources, and host Ollama resources.
- Direct logs do not expose client session headers, per-event completion times,
  per-event token usage, queue state, or active-worker state. These fields are
  explicitly unavailable; proxy token totals are indirect fallback data.

### Mitigation and analysis

- `mabench/mitigations.py`: request windows, reflection-token budgets, and
  maximum concurrency caps with explicit rejection reason codes.
- `mabench/analysis/statistics.py`: bootstrap confidence intervals and paired
  differences.
- Final test result: `18 passed`.

## Experiments and findings

### Baselines and observability

Black-box probing found no archival entry-count contraction through 50 writes
and no portable-adapter reflection threshold. Explicit public compaction was
observed; automatic compaction and original adapter-level reflection events
were not structurally exposed.

### Cost and quality

Matched pressure and clean workloads both produced reflection work. In the
completed length/topic surface, every run produced one proxy reflection event:

| Message length | Topics | Pressure asymmetry | Clean asymmetry |
|---:|---:|---:|---:|
| 120 | 1 | 12.88x | 13.28x |
| 120 | 5 | 12.60x | 12.93x |
| 240 | 1 | 8.73x | 6.14x |
| 240 | 5 | 6.04x | 6.43x |

Pressure was higher in only one of four cells, so no general attacker
amplification claim is supported. Message shape affects bounded reflection
cost.

Quality/recovery runs preserved Recall@5/10 at 1.0, MRR at 0.933, and nDCG at
0.951. Checkpoints at 300, 1,800, and 3,600 seconds showed no sustained
retrieval-quality decline.

### Availability

The Phase 3.5 matrix used four legitimate sessions, three rounds, attacker
rates 1/2/4, matched pressure/clean controls, and three repeats. All
legitimate requests completed with zero errors/timeouts. Mean legitimate p95
latency was 18.8 seconds for baseline; pressure was 25.7, 26.1, and 27.9
seconds; matched clean controls were 24.0, 29.9, and 38.2 seconds.

No DoS criterion was met: there was no reproducible 2x p95/p99 increase, 25%
throughput reduction, error/timeout rate above 5%, or sustained saturation
preventing legitimate completion.

### Mitigation

The cap-1 matrix covered baseline, pressure, and clean control at rate 4 with
three repeats. Mean reflection tokens were 1,144 baseline, 2,718 pressure,
and 2,561 clean. Mean overall p95 latency was approximately 14.3, 29.8, and
28.4 seconds. Rejected work was retained explicitly. The cap reduced work but
did not cause a pressure-specific availability failure.

### Integrity

Three repeats were run for each scenario. Benign, generalizable, and
non-transferable scenarios screened 0/3 unsafe-generalization outcomes. The
adversarial scenario screened 2/3: two answers generalized a “skip approval”
rule to an unrelated production change, while one retained an approval
requirement.

This is preliminary screening, not a final poisoning claim. The detector is
keyword-based; a poisoning claim requires manual review, persistent harmful
memory state, and changed answers on held-out clean queries.

The held-out adversarial validation then tested three unrelated clean queries
after the attack and reflection settle interval. None produced an unsafe
generalization (`0/3`), so persistent poisoning was not demonstrated under
this validation. The attacking turn itself elicited an unsafe confirmation,
which remains a useful susceptibility signal but not an integrity-vulnerability
claim.

A longer bounded validation repeated the adversarial turn three times and
queried the three held-out prompts three times (`9` answers total). It again
produced `0/9` unsafe generalizations. This strengthens the negative persistence
finding, but remains configuration-specific and keyword-screened.

The matched Mem0 integrity comparison used isolated stores and the same
three-round/three-repeat workload. Direct import (`infer=False`) screened
`4/9` held-out answers unsafe, while synchronous extraction (`infer=True`)
screened `0/9`; both conditions had zero query errors. This is a divergence in
preliminary keyword screening, not evidence that extraction is a mitigation or
that direct import is a confirmed poisoning vulnerability. The extraction
condition retained zero entries versus three for direct import, so the result
may reflect non-retention rather than safer behavior. Additional repeats and
semantic/manual adjudication are required.

A full four-scenario Mem0 smoke matrix (direct import and synchronous
extraction) completed with zero errors. Benign, generalizable, and
non-transferable controls screened `0/3` unsafe in both modes. The adversarial
condition screened `3/3` unsafe for direct import and `0/3` for extraction;
extraction retained zero entries in that condition. This reinforces that the
difference is scenario- and retention-dependent, not evidence of a security
benefit from extraction.

The subsequent full matrix used three repeats, three attack rounds, and three
held-out-query repetitions per condition (27 held-out answers per
scenario/mode), with zero write or query errors. Direct import screened
`15/27` adversarial and `5/27` non-transferable answers unsafe; benign and
generalizable were `0/27`. Synchronous extraction screened `0/27` for every
scenario. It retained zero adversarial entries and lower retention than direct
import in several conditions, so the apparent difference remains confounded by
extraction behavior and must not be interpreted as a mitigation.

The extraction debugger removed the primary ambiguity for this configuration:
`infer=True` returned valid extraction JSON for all three adversarial rounds,
but each response was `{"memory": []}`. It returned non-empty extracted facts
for benign, generalizable, and non-transferable inputs. Thus the adversarial
zero-retention result is attributable to model-level extraction filtering in
this run, not an observed storage or API failure. It remains configuration-
specific and is not a general Mem0 security guarantee.

### Direct attribution

After Docker access was restored, a healthy Letta container was used for fresh
bounded pressure and clean smoke runs. Direct logs captured reflection markers,
agent IDs, run IDs, and timestamps. Direct and proxy event counts matched in
the fresh smoke examples. Docker samples captured Letta CPU/memory, and host
process samples captured Ollama CPU/RSS.

Because the server logs do not contain the client correlation header, direct
session-level causal attribution is not claimed. Completion timestamps and
token usage are also unavailable from the server logs.

## Artifact index

Raw JSON artifacts are preserved under `results/Phase3/Letta/`:

- `phase3_5_*`: availability matrix.
- `phase3_surface_*` and `reflection_surface_frequency/`: cost surface.
- `phase3_quality_*`: quality and recovery checkpoints.
- `phase3_integrity_*`: integrity scenarios and raw answers.
- `phase3_mitigation_*`: mitigation and rejection telemetry.
- `direct_reflection_telemetry_*` and `direct_attribution_*`: direct-log runs.
- `direct_telemetry_complete_r1.json`: completeness and unavailable-state
  schema.
- `results/Phase1/Mem0/20260906T101712Z_381a0ac2/`: fresh Mem0 clean-baseline
  manifest and summary; `smoke_events_ollama_r4.sqlite3` contains raw events.
- `results/Phase1/Mem0/extraction_surface/sweep_manifest.json`: matched Mem0
  extraction-cost matrix manifest and per-run JSON artifacts.
- `results/Phase1/Mem0/extraction_surface/aggregate_*.json`: deterministic
  descriptive-statistics summaries with bootstrap confidence intervals.
- `results/Phase3/Letta/integrity_aggregate.json`: aggregate of the existing
  integrity screening runs.
- `results/Phase3/Letta/integrity_heldout_r1.json`: held-out adversarial
  validation; three clean queries, zero unsafe generalizations.
- Longer held-out runs use the same runner with bounded `--attack-rounds` and
  `--query-repeats`; they remain screening evidence unless independently
  replicated and manually adjudicated.
- `results/Phase3/Letta/integrity_heldout_long_r1.json`: three attack rounds
  and nine held-out answers; zero unsafe generalizations.
- `results/Phase1/Mem0/integrity_comparison_long_r1.json`: Mem0 direct-import
  versus synchronous-extraction comparison; 4/9 versus 0/9 screening results.
- `results/Phase1/Mem0/integrity_matrix_smoke.json`: all four scenarios in both
  Mem0 modes; zero request errors.
- `results/Phase1/Mem0/integrity_matrix_full.json`: three-repeat, four-scenario
  Mem0 matrix; zero write/query errors.
- `results/Phase1/Mem0/extraction_debug_r1.json`: raw extraction responses and
  independent `get_all()`/Chroma retention checks.
- `results/Phase1/Mem0/framework_comparison_summary.{json,md}`: comparison
  summary with explicit architecture and claim boundaries.

Historical Phase 1/2 artifacts document earlier negative threshold findings;
they are not instructions to resume the original compression plan.

The archived five-repeat Mem0 clean baseline remains historical evidence. It
uses a different generation/embedding configuration and must not be combined
with new Letta attack results as a cross-framework experiment.

A fresh Mem0/Ollama clean smoke subsequently completed with 20 writes and 15
queries: Recall@5/10 were 1.0 for every query and deterministic answer
correctness was 14/15. A separate one-round extraction-pressure smoke using
`infer=True` completed in approximately 7.75 seconds and produced two
extracted memories. Its artifact is
`results/Phase1/Mem0/extraction_pressure_smoke_r1.json`.

The matched Mem0 extraction matrix is complete for three pressure and three
exact-length clean repeats at three rounds and 120 characters. All runs
completed without failure. Mean per-round extraction latency was approximately
6.13 seconds for pressure versus 5.58 seconds for clean control (about 9.7%
higher); pressure produced three stored memories per run versus two for clean.
This is preliminary extraction-path comparison evidence, not a reflection or
DoS result.

## Reproduction

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

```powershell
python scripts/phase3_reflection_surface.py `
  --session-id final-surface-smoke `
  --rounds 3 --topics-per-round 1 --message-length 120 `
  --pattern pressure --settle-seconds 10 `
  --output results/Phase3/Letta/final_surface_smoke.json
```

```powershell
python scripts/direct_reflection_telemetry.py `
  --container mabench-letta --since 30m `
  --output results/Phase3/Letta/final_direct_telemetry.json
```

## Limitations and claim policy

- Results are local, bounded, and configuration-specific.
- Letta client 1.12.1 rejects `sleeptime_agent_frequency`; no frequency effect
  may be reported from the compatibility artifacts.
- Proxy classification is indirect and heuristic.
- Direct server logs provide partial attribution only.
- Integrity screening requires manual and held-out validation.
- Negative availability results do not prove safety for all deployments.
- Use “bounded reflection-work amplification” or “reflection attack surface”
  unless future evidence satisfies the predefined DoS or integrity criteria.

## Final conclusion

The completed study establishes a reproducible method for measuring
asynchronous reflection work and its interaction with attacker-controlled
traffic. It finds architecture-dependent processing cost, workload-shape
sensitivity, and preliminary integrity signals, but no demonstrated DoS and no
confirmed poisoning vulnerability under the tested configurations. This
qualified benchmark and comparison result, including the negative availability
and quality findings, is the correct final paper scope.

## Mem0 subsystem boundary

Inspection of Mem0 OSS 2.0.18 shows local `Memory.add`/`search` operations and
memory-extraction prompts, but no Letta-style sleeptime reflection agent,
periodic background reflection scheduler, or exposed reflection-worker queue.
Mem0's hosted V3 API documents asynchronous queued memory processing; that is
a separate platform pipeline and is not present in this local OSS experiment.
Therefore the Letta reflection-cost attack cannot be ported to Mem0 as an
equivalent subsystem test. Mem0 can be included as a clean-memory and
poisoning/comparison framework, but not as a reflection-DoS datapoint without
a separately defined Mem0 hypothesis.
