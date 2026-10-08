# MABench-RC Letta Environment

## Intended environment

- Windows host with Python 3.11.9 in `.venv`
- Docker Compose for the self-hosted Letta and PostgreSQL services
- Ollama running locally for generation
- `nomic-embed-text:latest` through Ollama for the current Letta/Mem0 runs
- SQLite for per-event experiment logging

The benchmark pins Python to `>=3.11,<3.12` because reported results must use
one stable interpreter version. Do not use the global Python 3.14 interpreter
for reported runs.

## Activate and install

```powershell
cd D:\Projects\LLM_MEMORY
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -e ".[dev]"
```

If the shell is not activated, use `.\.venv\Scripts\python.exe` explicitly.
After any dependency change, capture the complete environment with
`python -m pip freeze > requirements-lock.txt`.

The current local comparison uses Ollama models already provisioned on the
machine:

```powershell
ollama list
```

The reported current configuration uses `qwen2.5:1.5b-instruct` for
generation and `nomic-embed-text:latest` for embeddings. Keep benchmark runs
offline and deterministic after model provisioning. The older archived Mem0
baseline used a different Hugging Face embedding configuration and must not be
pooled with current results.

For the optional Mem0 track, install its pinned dependencies:

```powershell
python -m pip install -e ".[dev,mem0]"
```

Download the legacy embedding model only when reproducing the archived Phase 1
baseline:

```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

The adapter defaults `MABENCH_HF_LOCAL_FILES_ONLY=true` so a run cannot silently
change behavior because of a network lookup. Set it to `false` only when
intentionally provisioning a new model cache.

Letta runs use the self-hosted service defined in `docker-compose.letta.yml`.
The benchmark's own SQLite logging remains enabled.

## Start Letta

```powershell
docker compose -f docker-compose.letta.yml up -d letta-db letta
docker compose -f docker-compose.letta.yml ps
```

The host endpoint is `http://127.0.0.1:8283`. Experiment results are stored in
the repository's `results/` directory, separate from Letta's database volume.

## Start Ollama

The Ollama application/server must be running before any benchmark process uses
it. Verify the endpoint and selected models with `ollama list`; the current
reported setup uses `qwen2.5:1.5b-instruct` and
`nomic-embed-text:latest`.

If the CLI cannot connect, start the Ollama desktop application and retry. Do
not silently substitute another model in a reported experiment. Record the
model name, quantization, and Ollama version in the run manifest.

## Environment evidence for the paper

Before the first baseline run, save the outputs of Python, pip freeze, Docker,
Docker Compose, Ollama, hardware information, model identifiers, embedding
model, random seed, dataset revision, and clean-reset procedure. These values
belong in the run manifest and the methodology appendix.
