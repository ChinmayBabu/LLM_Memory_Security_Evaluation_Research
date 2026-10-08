import json
import sqlite3

from mabench.database import initialize_database
from mabench.manifest import create_run_manifest
from mabench.metrics import EventLogger
from mabench.metrics import score_answer
from mabench.adapters.letta_adapter import _field, _first


def test_manifest_is_unique_and_contains_reproducibility_fields(tmp_path):
    kwargs = {
        "system": "letta",
        "attack": "clean",
        "intensity": "low",
        "seed": 20260820,
        "config": {"repeats": 1},
        "models": {"llm": "test", "embedding": "test"},
    }
    first_id, first_path = create_run_manifest(tmp_path, **kwargs)
    second_id, second_path = create_run_manifest(tmp_path, **kwargs)

    assert first_id != second_id
    assert first_path != second_path
    manifest = json.loads(first_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == first_id
    assert manifest["environment"]["python_version"]


def test_database_schema_creates_run_and_event_tables(tmp_path):
    database_path = tmp_path / "events.sqlite3"
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"runs", "events"}.issubset(tables)


def test_event_logger_writes_per_event_record(tmp_path):
    database_path = tmp_path / "events.sqlite3"
    logger = EventLogger(database_path, "run-test")
    assert logger.log("write", entry_count=1, fixture_id="m01") == 0

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT event_type, entry_count, metadata_json FROM events"
        ).fetchone()
    assert row[0] == "write"
    assert row[1] == 1
    assert "m01" in row[2]


def test_answer_score_normalizes_number_words():
    assert score_answer("The benchmark requires 5 independent repeats.", ["five"])


def test_letta_search_result_uses_content_field():
    # Letta Passage objects expose `text`, while search Result objects expose
    # the same memory as `content`. The adapter must support both schemas.
    assert _field({"content": "stored fact"}, "content", "text") == "stored fact"
    assert _field({"text": "stored passage"}, "content", "text") == "stored passage"


def test_letta_passage_create_response_uses_first_passage():
    assert _field(_first([{"id": "p01", "text": "stored fact"}]), "id") == "p01"
