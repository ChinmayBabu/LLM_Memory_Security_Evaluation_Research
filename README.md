# MABench-RC

MABench-RC is a reproducible security benchmark and framework-comparison study
of attacker-controlled conversation traffic in LLM memory systems. Its main
track evaluates the asynchronous, sleeptime-reflection path in self-hosted
Letta. A separate Mem0/Chroma track evaluates synchronous extraction as an
architectural comparison; local Mem0 does not provide a Letta-equivalent
sleeptime reflection subsystem.

The implementation and bounded experiments are complete. The project is
research code, not a production security scanner or a claim that either
framework is generally secure or insecure.

## What was evaluated

- Letta black-box baselines and reflection-pressure workloads.
- Exact-length clean controls matched to pressure workloads.
- Reflection cost surfaces across message length and topic diversity.
- Concurrent legitimate traffic under attacker-rate pressure.
- Retrieval quality and recovery checkpoints.
- Request, token-budget, and reflection-concurrency mitigations.
- Preliminary memory-integrity scenarios with held-out clean queries.
- Direct Letta log parsing and evaluator-side proxy telemetry.
- Mem0 clean baselines, synchronous extraction cost, and exploratory
  direct-import versus extraction integrity comparisons.

Compression saturation and reflection-to-compression cascading are out of
scope. Historical Phase 1 and Phase 2 material remains in `docs/` for
provenance and must not be interpreted as the active research plan.

## Findings and claim boundaries

The final bounded evidence supports these conclusions:

- No reproducible denial-of-service condition was demonstrated. Legitimate
  requests completed in the tested availability matrix, and the predefined
  latency, throughput, error, and saturation thresholds were not met.
- Message shape changed bounded reflection cost, but pressure was higher than
  matched clean controls in only one of four completed surface cells. No
  general attacker-amplification claim is supported.
- Retrieval quality remained stable through the tested recovery checkpoints.
- An early Letta adversarial screen produced 2/3 unsafe-looking answers, but
  held-out validation produced 0/3, and a longer bounded validation produced
  0/9 unsafe unrelated-query answers. This is not a confirmed poisoning
  vulnerability.
- Mem0 results are preliminary, configuration-specific, and affected by
  retention behavior. They must not be described as a Mem0 reflection attack
  or as proof that synchronous extraction is a security mitigation.

See [docs/FINAL_END_TO_END_REPORT.md](docs/FINAL_END_TO_END_REPORT.md) for the
complete methodology, numerical results, artifact index, limitations, and
permitted claims.

## Repository layout

```text
mabench/                  Benchmark library, adapters, attacks, metrics
scripts/                  Experiment runners, proxy, collection, and analysis
tests/                    Unit and integration-style test coverage
docs/                     Methodology, environment, context, and reports
docker-compose.letta.yml  Self-hosted Letta and PostgreSQL/pgvector services
.env.example              Local configuration template
matrix.yaml               Historical experiment matrix configuration
schema.sql                SQLite event-log schema
```

Generated databases, caches, local environments, and experiment results are
ignored by Git. The documentation describes the result artifacts and their
locations so that runs can be reproduced locally without accidentally
committing large or machine-specific files.

## Requirements

- Windows host (the documented environment), Python 3.11.x, and Docker
  Compose.
- Ollama running locally with `qwen2.5:1.5b-instruct` and
  `nomic-embed-text:latest` provisioned.
- Optional Mem0 track dependencies: Mem0 OSS 2.0.18 and Chroma 1.5.9.

The project pins Python to `>=3.11,<3.12` for comparable reported runs. Do
not use a different interpreter or silently substitute models when reproducing
the reported results.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
ollama list
```

For the optional Mem0 track:

```powershell
python -m pip install -e ".[dev,mem0]"
```

Start the local model proxy and the self-hosted Letta services in separate
terminals:

```powershell
python scripts/local_model_proxy.py
docker compose -f docker-compose.letta.yml up -d letta-db letta
docker compose -f docker-compose.letta.yml ps
```

The proxy listens on `127.0.0.1:8787`, Letta on `127.0.0.1:8283`, and
PostgreSQL/pgvector on `127.0.0.1:5432`. Letta's Docker configuration routes
model and embedding requests through the local proxy. Ensure Ollama is already
running before starting benchmark scripts.

## Test and experiment commands

Run the automated checks with:

```powershell
python -m pytest -q
```

The completed project reports 18 passing tests. Example bounded runs are
documented in the phase methodology files; a representative reflection-surface
run is:

```powershell
python scripts/phase3_reflection_surface.py `
  --session-id phase3-surface-local-r1 `
  --rounds 3 `
  --topics-per-round 5 `
  --pattern pressure `
  --output results/Phase3/Letta/local_surface.json
```

Every run should use a fresh session, preserve its JSON output and manifest,
and record the model, embedding model, seed, environment, and reset procedure.
Use the commands and interpretation rules in
[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) and the phase-specific methodology
documents before treating a new run as comparable evidence.

## Documentation

- [Final end-to-end report](docs/FINAL_END_TO_END_REPORT.md) — findings,
  artifacts, limitations, and reproduction commands.
- [Project context](docs/PROJECT_CONTEXT.md) — final scope and claim policy.
- [Environment setup](docs/ENVIRONMENT.md) — supported local environment and
  reproducibility requirements.
- [Phase 1 documentation](docs/Phase1/) — archived baselines and methodology.
- [Phase 2 documentation](docs/Phase2/) — black-box probes and results.
- [Phase 3 documentation](docs/Phase3/) — reflection, availability,
  integrity, mitigation, and historical compaction work.

## License and status

No license has been selected yet. Add a `LICENSE` file before publishing this
repository if you want others to have explicit permission to use, modify, or
redistribute it. The current repository state is a completed research snapshot;
future experiments should be treated as separately approved extensions.
