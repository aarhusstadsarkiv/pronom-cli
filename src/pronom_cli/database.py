import sqlite3
from itertools import repeat
from pathlib import Path
from sqlite3 import Connection, Cursor

import orjson

from pronom_cli import logger

_CACHE_DIR = Path.home() / ".cache" / "pronom_cli"


def get_conn() -> Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(_CACHE_DIR / "database.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _create_formats_table(cursor: Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formats (
        id              INTEGER,
        source          TEXT NOT NULL,
        identifier      TEXT NOT NULL UNIQUE,
        name            TEXT NOT NULL,
        version         TEXT,
        description     TEXT NOT NULL,
        classification  TEXT,
        created_by      TEXT,
        creation_date   DATETIME,
        family          TEXT,

        PRIMARY KEY("id" AUTOINCREMENT)
    );
    """)


def _create_extensions_table(cursor: Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extensions (
        id              INTEGER,
        extension       TEXT NOT NULL,
        entry_id        INTEGER NOT NULL,

        PRIMARY KEY("id" AUTOINCREMENT),

        FOREIGN KEY (entry_id)
            REFERENCES formats(id)
            ON DELETE CASCADE
    );
    """)


def _create_sequences_table(cursor: Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sequences (
        id              INTEGER,
        entry_id        INTEGER NOT NULL,
        name            TEXT NOT NULL,
        note            TEXT,
        offset          INTEGER DEFAULT 0,
        max_offset      INTEGER DEFAULT 0,
        position        TEXT,
        sequence        TEXT,
        
        PRIMARY KEY("id" AUTOINCREMENT),

        FOREIGN KEY (entry_id)
            REFERENCES formats(id)
            ON DELETE CASCADE
    );
    """)


def _create_actions_table(cursor: Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id              INTEGER,
        entry_id        INTEGER NOT NULL,
        description     TEXT,
        action          TEXT,

        PRIMARY KEY("id" AUTOINCREMENT),

        FOREIGN KEY (entry_id)
            REFERENCES formats(id)
            ON DELETE CASCADE
    );
    """)


def _create_master_actions_table(cursor: Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_actions (
        id              INTEGER,
        entry_id        INTEGER NOT NULL,
        access          TEXT,
        statutory       TEXT,

        PRIMARY KEY("id" AUTOINCREMENT),

        FOREIGN KEY (entry_id)
            REFERENCES formats(id)
            ON DELETE CASCADE
    );
    """)


def _create_tables() -> None:
    with get_conn() as conn:
        cursor = conn.cursor()

        _create_formats_table(cursor)
        _create_extensions_table(cursor)
        _create_sequences_table(cursor)
        _create_actions_table(cursor)
        _create_master_actions_table(cursor)

        conn.commit()


def _populate_repository(path: Path) -> None:
    data = orjson.loads(path.read_bytes())

    with get_conn() as conn:
        cursor = conn.cursor()

        for key, data in data.items():
            # skip extension pointers
            if key.startswith("."):
                continue

            cursor.execute(
                """
                INSERT INTO formats (
                    source, identifier, name, version, description,
                    classification, created_by, creation_date, family
                ) VALUES ('PRONOM', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    data["name"],
                    data["version"],
                    data["description"],
                    data["types"],
                    data["created_by"],
                    data["created_date"],
                    data["family"],
                ),
            )
            entry_id = cursor.lastrowid
            conn.commit()

            extensions = data["extensions"]
            extensions_with_id = list(zip(extensions, repeat(entry_id)))

            cursor.executemany(
                """
                INSERT INTO extensions (extension, entry_id)
                VALUES (?, ?)
                """,
                extensions_with_id,
            )

            sequences = data["sequences"]
            sequences_with_id = [
                (entry_id, *sequence.values()) for sequence in sequences
            ]

            cursor.executemany(
                """
                INSERT INTO sequences(entry_id, name, note, offset, max_offset, position, sequence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                sequences_with_id,
            )


def initialize_database() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    db_file = _CACHE_DIR / "database.db"

    if db_file.exists():
        return

    repo_file = Path(__file__).parent / "repo.json"

    if not repo_file.exists():
        return

    logger.info("database file doesn't exist. creating tables...")

    _create_tables()

    logger.info("populating tables...")
    _populate_repository(repo_file)

    logger.info("everything is now finished.")

    # repo_file.unlink()
