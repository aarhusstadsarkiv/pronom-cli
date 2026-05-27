import json
from pathlib import Path

import httpx
import orjson
import pytest
import respx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pronom_cli.models.base import Base
from pronom_cli.models.models import Format
from pronom_cli.updater import (
    GITHUB_TAGS_URL,
    _get_github_latest_tag,
    _refresh_aca_if_new_tag,
)
from tests.conftest import (
    CUSTOM_SIGNATURES_YAML_EMPTY,
    FILEFORMATS_YAML,
    GITHUB_BASE,
)

_FILEFORMATS_URL = GITHUB_BASE + "fileformats.yml"
_CUSTOM_SIGS_URL = GITHUB_BASE + "custom_signatures.yml"

TAGS_RESPONSE = json.dumps([{"name": "v1.2.3"}, {"name": "v1.2.2"}])


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture()
def http_session():
    return httpx.Client()


@pytest.fixture()
def updater_file(tmp_path: Path) -> Path:
    path = tmp_path / "updater.json"
    path.write_bytes(orjson.dumps({"aca_tag": None}))
    return path


def test_get_github_latest_tag_returns_name(http_session: httpx.Client):
    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(
            return_value=httpx.Response(200, text=TAGS_RESPONSE)
        )
        result = _get_github_latest_tag(http_session)

    assert result == "v1.2.3"


def test_get_github_latest_tag_returns_none_on_error(http_session: httpx.Client):
    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(return_value=httpx.Response(403))
        result = _get_github_latest_tag(http_session)

    assert result is None


def test_get_github_latest_tag_returns_none_when_empty(http_session: httpx.Client):
    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(return_value=httpx.Response(200, text="[]"))
        result = _get_github_latest_tag(http_session)

    assert result is None


def test_refresh_aca_skips_when_tag_unchanged(
    engine, http_session: httpx.Client, updater_file: Path
):
    """When stored tag matches latest tag, no formats should be refreshed."""
    updater = {"aca_tag": "v1.2.3"}
    updater_file.write_bytes(orjson.dumps(updater))

    # Seed an ACA format
    with Session(engine) as session:
        session.add(
            Format(
                source="Fileformats",
                identifier="aca-fmt/1",
                name="Old Name",
                description="old",
            )
        )
        session.commit()

    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(
            return_value=httpx.Response(200, text=TAGS_RESPONSE)
        )
        _refresh_aca_if_new_tag(engine, http_session, updater, updater_file)

    # Format should not have been refreshed (name still "Old Name")
    with Session(engine) as session:
        fmt = session.scalars(select(Format)).one()
    assert fmt.name == "Old Name"

    # updater_file should not have been rewritten (aca_tag unchanged)
    written = orjson.loads(updater_file.read_bytes())
    assert written["aca_tag"] == "v1.2.3"


def test_refresh_aca_refreshes_when_new_tag(
    engine, http_session: httpx.Client, updater_file: Path
):
    """When a new tag is detected, all ACA formats are re-fetched and the tag is stored."""
    updater = {"aca_tag": "v1.0.0"}  # old tag
    updater_file.write_bytes(orjson.dumps(updater))

    # Seed an ACA format with a stale name
    with Session(engine) as session:
        session.add(
            Format(
                source="Fileformats",
                identifier="aca-fmt/1",
                name="Stale Name",
                description="stale",
            )
        )
        session.commit()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(GITHUB_TAGS_URL).mock(
            return_value=httpx.Response(200, text=TAGS_RESPONSE)
        )
        mock.get(_FILEFORMATS_URL).mock(
            return_value=httpx.Response(200, text=FILEFORMATS_YAML)
        )
        mock.get(_CUSTOM_SIGS_URL).mock(
            return_value=httpx.Response(200, text=CUSTOM_SIGNATURES_YAML_EMPTY)
        )

        _refresh_aca_if_new_tag(engine, http_session, updater, updater_file)

    # Format should have been refreshed
    with Session(engine) as session:
        fmt = session.scalars(select(Format)).one()
    assert fmt.name == "ACA Test Format"

    # updater_file should record the new tag
    written = orjson.loads(updater_file.read_bytes())
    assert written["aca_tag"] == "v1.2.3"


def test_refresh_aca_skips_when_tag_fetch_fails(
    engine, http_session: httpx.Client, updater_file: Path
):
    """When the GitHub API call fails, nothing is refreshed and no exception is raised."""
    updater = {"aca_tag": None}

    with Session(engine) as session:
        session.add(
            Format(
                source="Fileformats",
                identifier="aca-fmt/1",
                name="Untouched",
                description="desc",
            )
        )
        session.commit()

    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(return_value=httpx.Response(500))
        _refresh_aca_if_new_tag(engine, http_session, updater, updater_file)

    with Session(engine) as session:
        fmt = session.scalars(select(Format)).one()
    assert fmt.name == "Untouched"

    written = orjson.loads(updater_file.read_bytes())
    assert written["aca_tag"] is None


def test_refresh_aca_no_formats_in_db_still_updates_tag(
    engine, http_session: httpx.Client, updater_file: Path
):
    """When there are no ACA formats in the DB, the tag is still updated."""
    updater = {"aca_tag": "v1.0.0"}

    with respx.mock as mock:
        mock.get(GITHUB_TAGS_URL).mock(
            return_value=httpx.Response(200, text=TAGS_RESPONSE)
        )
        _refresh_aca_if_new_tag(engine, http_session, updater, updater_file)

    written = orjson.loads(updater_file.read_bytes())
    assert written["aca_tag"] == "v1.2.3"
