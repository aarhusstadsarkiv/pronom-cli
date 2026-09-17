from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from pronom_cli import database


def test_add_missing_columns_adds_fileformats_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE formats (id INTEGER PRIMARY KEY, source VARCHAR, name VARCHAR)"
            )
        )
    monkeypatch.setattr(database, "get_engine", lambda: engine)

    database._add_missing_columns()
    # running twice must not fail on an already-migrated database
    database._add_missing_columns()

    columns = {column["name"] for column in inspect(engine).get_columns("formats")}
    assert "fileformats_name" in columns
