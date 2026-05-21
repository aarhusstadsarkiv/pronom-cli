import re

import httpx
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pronom_cli.models.models import Format
from pronom_cli.repository.manager import RepositoryManager
from tests.conftest import PRONOM_HTML, PRONOM_XML, PRONOM_XML_NO_SIGS

_HTML_URL = re.compile(r"http://www\.nationalarchives\.gov\.uk/PRONOM/.*")
_XML_URL = re.compile(r"https://www\.nationalarchives\.gov\.uk/PRONOM/Format/.*")


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
    # expires_at=1 is far in the past, but PRONOM entries should still be
    # returned from cache because the expiry lookup key is case-sensitive and
    # "PRONOM" != "pronom", so expiration is None and the refresh branch is
    # never taken.
    fmt = Format(
        source="PRONOM",
        identifier="fmt/1",
        name="Cached",
        description="desc",
        expires_at=1,
    )
    db_session.add(fmt)
    db_session.flush()

    with respx.mock:
        result = manager.get_from_identifier("fmt/1")

    assert result is not None
    assert result.name == "Cached"


def test_non_aca_not_in_db_returns_none(manager: RepositoryManager):
    with respx.mock:
        result = manager.get_from_identifier("fmt/1")

    assert result is None


def test_aca_not_in_db_inserts_and_returns_format(
    manager: RepositoryManager, db_session: Session
):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert result.identifier == "aca-fmt/1"
    assert result.name == "Test Format"
    assert result.source == "PRONOM"

    count = db_session.scalar(
        select(func.count(Format.id)).where(Format.identifier == "aca-fmt/1")
    )
    assert count == 1


def test_aca_not_in_db_attaches_extensions(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert len(result.extensions) == 1
    assert result.extensions[0].extension == "txt"


def test_aca_not_in_db_attaches_sequences(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert len(result.sequences) == 1
    assert result.sequences[0].sequence == "AABBCC"
    assert result.sequences[0].position == "BOF"


def test_aca_no_sigs_in_xml(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(
            return_value=httpx.Response(200, text=PRONOM_XML_NO_SIGS)
        )

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is not None
    assert result.extensions == []
    assert result.sequences == []


def test_pronom_html_has_no_form_returns_none(
    manager: RepositoryManager, db_session: Session
):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(
            return_value=httpx.Response(
                200, text="<html><body>no form here</body></html>"
            )
        )

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is None
    count = db_session.scalar(select(func.count(Format.id)))
    assert count == 0


def test_pronom_xml_non_200_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(500))

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is None


def test_pronom_xml_parse_error_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text="not xml at all"))

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is None


def test_pronom_xml_reports_error_returns_none(manager: RepositoryManager):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(
            return_value=httpx.Response(
                200, text="The following errors were reported: bad puid"
            )
        )

        result = manager.get_from_identifier("aca-fmt/1")

    assert result is None


def test_pronom_upsert_updates_existing_row(
    manager: RepositoryManager, db_session: Session
):
    existing = Format(
        source="PRONOM",
        identifier="aca-fmt/1",
        name="Old Name",
        description="old desc",
    )
    db_session.add(existing)
    db_session.flush()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(_HTML_URL).mock(return_value=httpx.Response(200, text=PRONOM_HTML))
        mock.get(_XML_URL).mock(return_value=httpx.Response(200, text=PRONOM_XML))

        result = manager._get_from_pronom("aca-fmt/1")

    assert result is not None
    assert result.name == "Test Format"

    count = db_session.scalar(
        select(func.count(Format.id)).where(Format.identifier == "aca-fmt/1")
    )
    assert count == 1
