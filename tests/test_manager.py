import re

import httpx
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pronom_cli.models.models import Format
from pronom_cli.repository.manager import RepositoryManager
from tests.conftest import (
    CUSTOM_SIGNATURES_YAML,
    CUSTOM_SIGNATURES_YAML_EMPTY,
    FILEFORMATS_YAML,
    FILEFORMATS_YAML_EMPTY,
    FILEFORMATS_YAML_NO_EXTS,
    GITHUB_BASE,
    PRONOM_HTML,
    PRONOM_XML,
)

_HTML_URL = re.compile(r"http://www\.nationalarchives\.gov\.uk/PRONOM/.*")
_XML_URL = re.compile(r"https://www\.nationalarchives\.gov\.uk/PRONOM/Format/.*")
_FILEFORMATS_URL = GITHUB_BASE + "fileformats.yml"
_CUSTOM_SIGS_URL = GITHUB_BASE + "custom_signatures.yml"


def _mock_github(mock: respx.MockRouter, fileformats: str, signatures: str) -> None:
    mock.get(_FILEFORMATS_URL).mock(return_value=httpx.Response(200, text=fileformats))
    mock.get(_CUSTOM_SIGS_URL).mock(return_value=httpx.Response(200, text=signatures))


def test_returns_format_found_in_db(manager: RepositoryManager, db_session: Session):
    fmt = Format(source="PRONOM", identifier="fmt/1", name="Test", description="desc")
    db_session.add(fmt)
    db_session.flush()

    with respx.mock:
        result = manager.get_from_identifier("fmt/1")

    assert result is not None
    assert result.identifier == "fmt/1"
    assert result.name == "Test"


def test_pronom_source_never_expires(manager: RepositoryManager, db_session: Session):
    fmt = Format(
        source="PRONOM",
        identifier="fmt/1",
        name="Cached",
        description="desc",
        expires_at=None,
    )
    db_session.add(fmt)
    db_session.flush()

    with respx.mock:
        result = manager.get_from_identifier("fmt/1")

    assert result is not None
    assert result.name == "Cached"


def test_aca_not_in_db_fetches_from_github(
    manager: RepositoryManager, db_session: Session
):
    with respx.mock(assert_all_called=False) as mock:
        _mock_github(mock, FILEFORMATS_YAML, CUSTOM_SIGNATURES_YAML_EMPTY)

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert result.identifier == "aca-fmt/1"
    assert result.name == "ACA Test Format"
    assert result.source == "Fileformats"

    count = db_session.scalar(
        select(func.count(Format.id)).where(Format.identifier == "aca-fmt/1")
    )
    assert count == 1


def test_aca_not_in_db_attaches_extensions(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        _mock_github(mock, FILEFORMATS_YAML, CUSTOM_SIGNATURES_YAML_EMPTY)

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert len(result.extensions) == 1
    assert result.extensions[0].extension == ".tst"


def test_aca_not_in_db_attaches_sequences_from_custom_sigs(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        _mock_github(mock, FILEFORMATS_YAML, CUSTOM_SIGNATURES_YAML)

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert len(result.sequences) == 1
    assert result.sequences[0].sequence == "AABBCC"
    assert result.sequences[0].position == "BOF"


def test_aca_not_in_db_no_extensions_no_sequences(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        _mock_github(mock, FILEFORMATS_YAML_NO_EXTS, CUSTOM_SIGNATURES_YAML_EMPTY)

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert result.extensions == []
    assert result.sequences == []


def test_aca_not_in_fileformats_returns_none(
    manager: RepositoryManager, db_session: Session
):
    with respx.mock(assert_all_called=False) as mock:
        _mock_github(mock, FILEFORMATS_YAML_EMPTY, CUSTOM_SIGNATURES_YAML_EMPTY)

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is None
    count = db_session.scalar(select(func.count(Format.id)))
    assert count == 0


def test_get_from_pronom_inserts_format(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager._get_from_pronom("fmt/1")

    assert result is not None
    assert result.identifier == "fmt/1"
    assert result.name == "Test Format"
    assert result.source == "PRONOM"


def test_get_from_pronom_upserts_existing_row(
    manager: RepositoryManager, db_session: Session
):
    existing = Format(
        source="PRONOM",
        identifier="fmt/1",
        name="Old Name",
        description="old desc",
    )
    db_session.add(existing)
    db_session.flush()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager._get_from_pronom("fmt/1")

    assert result is not None
    assert result.name == "Test Format"

    count = db_session.scalar(
        select(func.count(Format.id)).where(Format.identifier == "fmt/1")
    )
    assert count == 1


def test_get_from_pronom_html_no_form_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(
            return_value=httpx.Response(200, text="<html><body>no form</body></html>")
        )

        result = manager._get_from_pronom("fmt/1")

    assert result is None


def test_get_from_pronom_xml_non_200_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(500))

        result = manager._get_from_pronom("fmt/1")

    assert result is None


def test_get_from_pronom_xml_parse_error_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text="not xml"))

        result = manager._get_from_pronom("fmt/1")

    assert result is None


def test_get_from_pronom_xml_error_message_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(
            return_value=httpx.Response(
                200, text="The following errors were reported: bad puid"
            )
        )

        result = manager._get_from_pronom("fmt/1")

    assert result is None
