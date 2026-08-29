import json

from scripts.migrate_to_vector_db import migrate


def test_migration_vectors_records_without_mutating_sources(tmp_path):
    memory = tmp_path / "memory.json"
    diary = tmp_path / "diary.json"
    output = tmp_path / "vectors.json"
    memory.write_text(json.dumps({"facts": {"language": "Python"}}))
    diary.write_text(json.dumps({"entries": [{"content": "Project note"}]}))

    count = migrate(memory, diary, output)

    assert count == 2
    data = json.loads(output.read_text())
    assert len(data["records"]) == 2
    assert all(len(record["embedding"]) == 384 for record in data["records"])
    assert json.loads(memory.read_text())["facts"]["language"] == "Python"


def test_migration_dry_run_does_not_write_output(tmp_path):
    memory = tmp_path / "memory.json"
    diary = tmp_path / "diary.json"
    output = tmp_path / "vectors.json"
    memory.write_text(json.dumps({"facts": {"x": "y"}}))
    diary.write_text("[]")

    assert migrate(memory, diary, output, dry_run=True) == 1
    assert not output.exists()
