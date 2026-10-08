# Phase 3 Letta Public Compaction Observation (Historical)

> Final-state note: this historical methodology is retained for provenance.
> The completed paper scope is reflection-only; compression and cascading
> plans are superseded. See `docs/FINAL_END_TO_END_REPORT.md`.

## Objective

Phase 3 evaluates Letta's conversation compaction through its documented public
API. It is separate from Phase 2 archival-passage threshold probing and does
not infer an automatic threshold.

## Procedure

1. Create a fresh Letta agent/session.
2. Send a controlled number of short conversation messages.
3. List messages before compaction.
4. Invoke `agents.messages.compact()` with sliding-window settings.
5. List messages after compaction.
6. Preserve the returned summary and before/after statistics.

```powershell
python scripts/phase3_compaction.py `
  --session-id phase3-letta-compaction-20260827-r1 `
  --messages 8 `
  --output results/Phase3/Letta/phase3_compaction_20260827_r1.json
```

## Interpretation

A compaction response containing a summary and before/after counts is direct
evidence that the public compaction operation executed. It is not evidence of
the automatic trigger threshold. Reflection and sleep-time activity remain
unobservable unless exposed by a public response or event endpoint.

Record the Letta version, model, embedding, context limit, compaction mode,
messages sent, counts, summary, latency, errors, and hardware limitations.
Do not combine these observations with Phase 2 archival-contraction results.

## Next experiment: automatic-compaction stress

The explicit-compaction trial does not estimate Letta's automatic trigger. The
next implementation must retain each `messages.create()` response with
`include_compaction_messages=True`, then detect structured summary or
compaction-event messages while sending 8, 16, and 32 short messages. Run three
fresh sessions per condition. Record automatic event presence, message counts,
summary content, latency, resource usage where feasible, and errors/OOMs.

If no automatic event appears, report automatic compaction as not observed in
the tested message range. Do not describe this as proof that compaction is
absent. Reflection-loop cost asymmetry remains out of scope until reflection
events and system token usage become observable.

## Instrumentation-first reflection track

The reflection-loop attack is a separate track and must not begin from timing
or compaction evidence alone. The evaluator instruments the local model proxy
and captures Letta response event messages using correlation IDs. The proxy
records model request latency and prompt/completion/total token usage; it does
not expose this telemetry to the attacker.

Run the validation harness before any reflection attack:

```powershell
python scripts/reflection_instrumentation.py `
  --session-id phase3-reflection-instrumentation-r1 `
  --messages 8 `
  --output results/Phase3/Letta/reflection_instrumentation_r1.json
```

The gate passes only when structured reflection events are directly observed,
reflection work is distinguishable from ordinary user-turn and compaction
requests, and nonzero model token usage is attributable to those events. A
clean no-reflection control must produce no false positives. If the gate does
not pass on Letta OSS `0.16.8`, the result is an instrumentation feasibility
limitation; no reflection-loop claim is permitted. The existing automatic
compaction trials remain a distinct, valid non-detection experiment.

## Instrumentation validation result

Validation artifact: `results/Phase3/Letta/reflection_instrumentation_r2.json`.
Letta returned nonzero per-turn usage statistics totaling 2,622 model tokens
across four turns, so wrapper-level token telemetry is available. However, no
structured compaction or reflection event was returned, and no reflection work
could be directly attributed to an attacker turn. The gate status is therefore
`instrumentation_incomplete`. This is an instrumentation feasibility result,
not a negative result about Letta's internal reflection implementation.

The local proxy has evaluator-only telemetry endpoints at `/telemetry/events`.
The running proxy process must be restarted with the instrumented code before
proxy-level request telemetry is available. Letta's response usage remains the
current usable token signal, but it does not by itself separate reflection
tokens from ordinary turn tokens.

## Letta server-side source finding

Read-only inspection of the running `letta/letta:0.16.8` image identified the
active reflection path. `utils.py` constructs a `SleeptimeMultiAgentV4` when
the agent has a sleeptime group; `run_sleeptime_agents()` creates a background
run, and `_participant_agent_step()` invokes a separate sleeptime agent step
with a prompt explicitly identifying it as a background memory-management
agent. Recent server logs confirmed these sleeptime-agent model requests.

This establishes where direct instrumentation must attach, but source-path
evidence alone is not yet the attack telemetry artifact. The proxy classifier
must be restarted and the validation rerun so sleeptime requests receive a
separate request class and attributable token totals.

## Phase 3.5: concurrent availability impact

The matched pressure/control and quality/recovery results do not support a
quality-degradation or positive-feedback-loop claim. The next experiment tests
whether attributable sleeptime work affects service availability under
concurrent legitimate traffic.

Use one bounded pressure attacker and four legitimate user sessions. Run a
legitimate-only baseline, then low, medium, and high attacker rates. Every
condition uses identical message lengths, duration, concurrency, and three
fresh repeats. Preserve correlation IDs for attacker and legitimate requests.

Record p50/p95/p99 latency, throughput, completed requests, errors, timeouts,
and queueing delay where available. Sample evaluator-host CPU and RSS, and
join the run with proxy foreground/sleeptime request classes, token counts,
and reflection event counts. Keep retrieval and answer measurements as a
secondary impact track.

A positive availability result requires both attributable reflection work and a
reproducible matched-control effect: at least 2x p95/p99 latency, at least 25%
throughput loss, more than 5% errors/timeouts, or sustained saturation that
prevents legitimate requests from completing. Increased reflection work with
no such effect is a bounded-cost result, not a DoS claim.

## Reflection-cost mitigation implementation

The evaluator proxy now supports three opt-in reflection controls:

- `MABENCH_REFLECTION_REQUESTS_PER_WINDOW` for per-session request admission;
- `MABENCH_REFLECTION_TOKENS_PER_WINDOW` for a global token budget;
- `MABENCH_REFLECTION_MAX_CONCURRENT` for a background-reflection concurrency cap.

Rejected requests are retained in proxy telemetry with status 429 and an
explicit mitigation reason. Successful requests reconcile reserved and actual
token usage, so mitigation results report both blocked work and completed work.
The mitigation smoke requires restarting the proxy with one control enabled;
the existing proxy process was not forcibly terminated during implementation.

The direct collector is implemented in `scripts/direct_reflection_telemetry.py`
and emits the required event schema or an explicit unavailable status. The
current environment does not grant Docker API access, so direct server logs
must remain a fallback-aware limitation until the collector is run with Docker
permissions. The integrity runner is implemented in
`scripts/phase3_reflection_integrity.py`; its benign smoke completed without an
unsafe-generalization signal.

## Reflection-cost characterization extension

If the availability matrix remains negative, continue with a reflection-only
cost surface. Vary message rate, burst/sustained scheduling, message length,
topic diversity, concurrent sessions, sleeptime frequency, and model
configuration. Use legitimate-only, attacker-only, combined, exact-length
clean, and no-sleeptime controls where the deployment supports them.

For each condition, compute incremental reflection work over the legitimate
baseline, reflection tokens per attacker token, estimated monetary or energy
cost where measurable, CPU/RSS, queueing, co-running throughput, and p95/p99
latency. Preserve all raw request and proxy events.

Evaluate per-session rate limiting, a global reflection budget, and a
background-worker concurrency cap. Report their cost reduction, benign quality
impact, false-positive rate, and clean-traffic overhead. A reflection-cost
finding remains distinct from a DoS finding unless the predefined
control-relative availability thresholds are met.
