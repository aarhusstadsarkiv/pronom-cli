import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx
import orjson
from bs4 import BeautifulSoup, Tag
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from pronom_cli import logger
from pronom_cli.database import get_engine
from pronom_cli.models.models import Format
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.utils import Filter

UPDATES_URL = "https://www.nationalarchives.gov.uk/aboutapps/pronom/release-notes.xml"


def lookup_puid(
    engine: Engine,
    http_session: httpx.Client,
    puid: str,
    handled_puids: set[str],
    lock: threading.Lock,
) -> None:
    try:
        with Session(engine) as session:
            repository = RepositoryManager(session, http_session, [Filter.PRONOM])
            repository._get_from_pronom(puid)
            session.commit()
    except Exception as e:
        logger.error(f"an exception was raised for {puid}: {e}")
        return

    with lock:
        handled_puids.add(puid)
    logger.info(f"successfully updated {puid}")


def handle_expired_format() -> None: ...


def _parse_release_date(release: Tag) -> datetime | None:
    date = release.find("release_date")

    if not date or not date.text:
        return

    return datetime.strptime(
        re.sub(r"(\d)(st|nd|rd|th)", r"\1", date.text.strip()), "%d %B %Y"
    )


def _refresh_expired(engine: Engine, http_session: httpx.Client) -> None:
    with Session(engine) as session:
        expired = session.scalars(
            select(Format).where(
                Format.expires_at.isnot(None),
                Format.expires_at < int(time.time()),
            )
        ).all()
        identifiers = [fmt.identifier for fmt in expired]

    if not identifiers:
        logger.info("no expired formats found.")
        return

    logger.info(f"found {len(identifiers)} expired format(s), refreshing...")

    def _refresh(identifier: str) -> None:
        try:
            with Session(engine) as db_session:
                repository = RepositoryManager(
                    db_session, http_session, [Filter.PRONOM, Filter.FILEFORMATS]
                )

                # PRONOM entries gets updated (if needed) later in updater.py
                if not identifier.startswith("aca-"):
                    return

                repository._get_from_fileformats(identifier)
                db_session.commit()

        except Exception as e:
            logger.error(f"failed to refresh expired format {identifier}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_refresh, identifier) for identifier in identifiers]
        for future in futures:
            future.result()


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
    """
    updater_file = Path(__file__).parent / "updater.json"
    updater = orjson.loads(updater_file.read_bytes())

    engine = get_engine()

    with httpx.Client() as http_session:
        logger.info("refreshing all expired formats...")
        _refresh_expired(engine, http_session)
        logger.info("finished refreshed expired formats")

        logger.info("updating pronom repository...")

        response = http_session.get(UPDATES_URL)
        html = response.text

        soup = BeautifulSoup(html, "xml")
        releases = soup.find_all("release_note")

        if not releases:
            logger.error("no releases were found. this shouldn't happen")
            return

        updater_date = datetime.fromisoformat(updater["updated_version"])

        if _parse_release_date(releases[0]) == updater_date:
            logger.info("no new releases from pronom.")
            return

        with Session(engine) as session:
            before = session.scalar(select(func.count()).select_from(Format)) or 0

        handled_puids: set[str] = set()
        lock = threading.Lock()

        # process releases oldest-first to prevent stale overwrites
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
                    futures = [
                        executor.submit(
                            lookup_puid, engine, http_session, p, handled_puids, lock
                        )
                        for p in puids
                    ]
                    for future in futures:
                        future.result()

            logger.info(f"successfully updated to {date.strftime('%d %B %Y')}")

            # clear so a newer release of the same format gets updated correctly
            with lock:
                handled_puids.clear()

            updater["last_updated"] = datetime.now().isoformat()
            updater["updated_version"] = date.isoformat()
            updater_file.write_bytes(orjson.dumps(updater))

        with Session(engine) as session:
            after = session.scalar(select(func.count()).select_from(Format)) or 0

    added = after - before
    logger.info(f"finished updating pronom repository (added {added} new formats)")
