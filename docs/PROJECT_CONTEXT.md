# MABench-RC: Final Reflection-Subsystem Benchmark Context

The final project is a security benchmark and framework-comparison study of
attacker-controlled conversation traffic against
Letta OSS sleeptime reflection, with a new Mem0 comparative track implemented
for external validity. The Letta track is complete; Mem0 now has a fresh clean
baseline and a matched extraction-cost matrix. The paper must not claim a Mem0
reflection attack because local Mem0 has no equivalent sleeptime subsystem.
Compression and reflection-to-compression cascading are excluded.

The study covers black-box baselines, pressure versus exact-length clean
controls, quality/recovery, concurrent availability, cost surface, mitigation,
preliminary integrity evaluation, and direct Letta-log attribution where
available. Proxy telemetry is retained as an explicitly indirect fallback.

The final evidence, commands, artifact index, limitations, and claim policy
are in [FINAL_END_TO_END_REPORT.md](FINAL_END_TO_END_REPORT.md). Raw JSON
artifacts under `results/Phase3/Letta/` are preserved as the numeric source.

Held-out integrity validation produced 0/3 unsafe unrelated-query answers
after an adversarial turn. A longer bounded run produced 0/9 after three attack
rounds and three query repetitions. Treat the earlier 2/3 unsafe screen as
preliminary, not as confirmed poisoning.

Mem0 comparison screening produced 4/9 unsafe answers with direct import and
0/9 with synchronous extraction in one matched run. Treat this as preliminary
and configuration-specific until repeated and manually adjudicated.

Future work must be a separately approved extension. Do not infer a DoS or
poisoning result from reflection-token growth alone, and do not restart the
abandoned compression/cascading plan under this context.
