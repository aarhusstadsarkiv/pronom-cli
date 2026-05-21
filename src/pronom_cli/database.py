import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import orjson
from fast_yaml import Loader, load
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from pronom_cli import logger, service
from pronom_cli.models.action import parse_action
from pronom_cli.models.base import Base
from pronom_cli.models.models import Action, Extension, Format, Sequence
from pronom_cli.utils import search_custom_signatures

_CACHE_DIR = Path.home() / ".cache" / "pronom_cli"
_DB_PATH = _CACHE_DIR / "database.db"
ENGINE = create_engine(f"sqlite:///{str(_DB_PATH)}", echo=False, future=True)


def get_engine() -> Engine:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return ENGINE


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


def _load_from_github(filename: str) -> Any:
    response = service.session.get(
        f"https://raw.githubusercontent.com/aarhusstadsarkiv/reference-files/refs/heads/main/{filename}"
    )
    if response.status_code != 200:
        logger.error(f"failed to fetch {filename} from github")
        return
    return load(response.text, Loader=Loader)


def _populate_from_pronom(
    session: Session, pronom_data: dict[str, Any]
) -> dict[str, Format]:
    """Populate database with PRONOM data from repo.json."""
    formats_map: dict[str, Format] = {}
    for key, item in pronom_data.items():
        if key.startswith("."):
            continue

        fmt = Format(
            source="PRONOM",
            identifier=key,
            name=item["name"],
            version=item.get("version"),
            description=item["description"],
            classification=item.get("types"),
            created_by=item.get("created_by"),
            creation_date=item.get("created_date"),
            family=item.get("family"),
        )

        fmt.extensions = [
            Extension(extension=ext) for ext in item.get("extensions", [])
        ]
        fmt.sequences = [
            Sequence(
                name=s.get("name"),
                note=s.get("note"),
                offset=s.get("offset", 0),
                max_offset=s.get("max_offset", 0),
                position=s.get("position"),
                sequence=s.get("sequence"),
            )
            for s in item.get("sequences", [])
        ]
        session.add(fmt)
        formats_map[key] = fmt
    return formats_map


def _populate_from_fileformats(
    session: Session,
    fileformats_data: dict[str, Any],
    custom_signatures: list[dict[str, Any]],
    formats_map: dict[str, Format],
) -> None:
    """Populate database with data from fileformats.yml and custom_signatures.yml."""
    for puid, data in fileformats_data.items():
        fmt = formats_map.get(puid)

        if not fmt:
            if not puid.startswith("aca-fmt"):
                continue

            fmt = Format(
                source="Fileformats",
                identifier=puid,
                name=data["name"],
                description=data.get("description", "No description provided"),
                expires_at=int(time.time() + timedelta(days=1).seconds),
            )
            session.add(fmt)

        if not fmt.extensions:
            fmt.extensions = [
                Extension(extension=ext) for ext in data.get("extensions", [])
            ]

        if not fmt.action:
            fmt.action = Action(
                description=data.get("description"),
                action=str(parse_action(data)),
            )

        if puid.startswith("aca-fmt"):
            _add_custom_sequences(fmt, custom_signatures, puid)


def _add_custom_sequences(
    fmt: Format, custom_signatures: list[dict[str, Any]], puid: str
) -> None:
    """Search for and add custom BOF/EOF sequences to an ACA format."""
    seq_from_yml = search_custom_signatures(custom_signatures, puid)
    if not seq_from_yml:
        return

    name = seq_from_yml["signature"]
    note = seq_from_yml.get("description", "")

    for key, label in (("bof", "BOF"), ("eof", "EOF")):
        sequence = seq_from_yml.get(key)
        if not sequence:
            continue

        fmt.sequences.append(
            Sequence(
                name=name,
                note=note,
                offset=0,
                max_offset=0,
                position=label,
                sequence=sequence,
            )
        )


def populate_repository(path: Path) -> None:
    """
    Load data from multiple sources and populate the database.

    This function orchestrates the loading of PRONOM data from a local
    `repo.json` and supplementary data from remote YAML files, then
    populates the database within a single transaction.
    """
    pronom_data = orjson.loads(path.read_bytes())
    fileformats_data = _load_from_github("fileformats.yml")
    custom_signatures_data = _load_from_github("custom_signatures.yml")

    engine = get_engine()
    with Session(engine) as session:
        try:
            with session.begin():
                # Process PRONOM data first and get a map of created formats
                formats_map = _populate_from_pronom(session, pronom_data)

                # Use the map to efficiently link and supplement with fileformats data
                _populate_from_fileformats(
                    session, fileformats_data, custom_signatures_data, formats_map
                )

        except Exception as e:
            session.rollback()
            raise RuntimeError(f"Failed to populate database: {e}") from e


def initialize_database() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if _DB_PATH.exists():
        return

    repo_file = Path(__file__).parent / "repo.json"
    if not repo_file.exists():
        return

    logger.info("database file doesn't exist. creating tables...")

    create_tables()

    logger.info("populating tables...")
    populate_repository(repo_file)

    logger.info("everything is now finished.")

    # repo_file.unlink()
