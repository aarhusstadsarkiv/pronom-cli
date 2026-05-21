import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx
import orjson
from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session

from pronom_cli import logger
from pronom_cli.database import get_engine
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.utils import Filter

UPDATES_URL = "https://www.nationalarchives.gov.uk/aboutapps/pronom/release-notes.xml"
PUID_LOOKUP_URL = "http://www.nationalarchives.gov.uk/PRONOM/"

handled_puids: set[str] = set()
_handled_lock = threading.Lock()


def lookup_puid(repository: RepositoryManager, puid: str) -> None:
    try:
        repository._get_from_pronom(puid)
    except Exception as e:
        logger.error(f"an exception was raised for {puid}: {e}")
        return

    with _handled_lock:
        handled_puids.add(puid)
    logger.info(f"successfully updated {puid}")


def _parse_release_date(release: Tag) -> datetime | None:
    date = release.find("release_date")

    if not date or not date.text:
        return

    return datetime.strptime(
        re.sub(r"(\d)(st|nd|rd|th)", r"\1", date.text.strip()), "%d %B %Y"
    )


def update() -> None:
    """
    Updates the local PRONOM repository by checking for new release notes on the update URL
    and incorporating newly identified formats into the repository. This function retrieves
    the latest updates, processes the release notes in reverse order, and updates the repository
    accordingly.

    Raises:
        httpx.HTTPError: If there is an issue with the HTTP request to fetch release notes.
        orjson.JSONDecodeError: If there is an issue decoding the updater JSON file.
        ValueError: If there is an issue parsing release date formats from release notes.

    Parameters:
        None

    Returns:
        None
    """
    logger.info("forcefully updating all expired formats")
    # TODO: handle expired formats
    logger.info("succesfully purged or updated expired formats")

    logger.info("updating pronom repository...")

    updater_file = Path(__file__).parent / "updater.json"
    updater = orjson.loads(updater_file.read_bytes())

    engine = get_engine()
    http_session = httpx.Client()

    response = http_session.get(UPDATES_URL)
    html = response.text

    soup = BeautifulSoup(html, "xml")

    releases = soup.find_all("release_note")

    if not releases:
        logger.error("no releases were found. this shouldn't happen")

    with Session(engine) as db_session:
        repository = RepositoryManager(
            db_session,
            http_session,
            [
                Filter.PRONOM,
                Filter.FILEXT,
                Filter.FILEFORMATS,
                Filter.FILEPROINFO,
                Filter.FILEINFO,
            ],
        )

        before = ...  # TODO: count the whole formats table
        updater_date = datetime.fromisoformat(updater["updated_version"])

        if _parse_release_date(releases[0]) == updater_date:
            logger.info("no new releases from pronom.")
            return

        # looking through the releases in reversed order to prevent wrongly updated formats
        for release in releases[::-1]:
            date = _parse_release_date(release)

            if not date or updater_date > date:
                continue

            formats = release.find_all("format")
            puids = []

            for format in formats:
                puid_tag = format.find("puid")
                fmt_type = puid_tag.attrs.get("type")  # type: ignore
                puid = f"{fmt_type}/{puid_tag.text.strip()}"  # type: ignore

                # puids can appear in multiple release records
                if puid in handled_puids:
                    continue

                puids.append(puid)

            if puids:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(lookup_puid, repository, p) for p in puids]
                    for future in futures:
                        future.result()

            db_session.commit()

            logger.info(f"successfully updated to {date.strftime('%d %B %Y')}")

            # after we've handled all the formats for the current update
            # we must empty handled_puids, so if there is a newer update
            # of the format, it gets correctly updated.
            with _handled_lock:
                handled_puids.clear()

            updater["last_updated"] = datetime.now()
            updater["updated_version"] = date
            updater_file.write_bytes(orjson.dumps(updater))

        after = ...  # TODO: coutn the whole formats table
        logger.info("finished updating pronom repository (added X new formats)")
