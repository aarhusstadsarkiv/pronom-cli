import asyncio
import re
from datetime import datetime
from pathlib import Path

import aiohttp
import orjson
from bs4 import BeautifulSoup

from pronom_cli import logger, service
from pronom_cli.repository.pronom import PronomRepository

UPDATES_URL = "https://www.nationalarchives.gov.uk/aboutapps/pronom/release-notes.xml"
PUID_LOOKUP_URL = "http://www.nationalarchives.gov.uk/PRONOM/"

handled_puids = set()


async def lookup_puid(repository: PronomRepository, puid: str) -> None:
    try:
        await repository._get_from_pronom(puid, False)
    except Exception as e:
        logger.error(f"an exception was raised for {puid}: {e}")
        return

    handled_puids.add(puid)
    logger.info(f"successfully updated {puid}")


async def update() -> None:
    """
    Updates the local PRONOM repository by checking for new release notes on the update URL
    and incorporating newly identified formats into the repository. This function retrieves
    the latest updates, processes the release notes in reverse order, and updates the repository
    accordingly.

    Raises:
        aiohttp.ClientError: If there is an issue with the HTTP request to fetch release notes.
        orjson.JSONDecodeError: If there is an issue decoding the updater JSON file.
        ValueError: If there is an issue parsing release date formats from release notes.

    Parameters:
        None

    Returns:
        None
    """
    service.session = aiohttp.ClientSession()

    updater_file = Path(__file__).parent / "updater.json"
    updater = orjson.loads(updater_file.read_bytes())

    repository = await PronomRepository.load()

    response = await service.session.get(UPDATES_URL)
    html = await response.text()

    soup = BeautifulSoup(html, "xml")

    releases = soup.find_all("release_note")

    if not releases:
        logger.error("no releases were found. this shouldn't happen")

    before = len(repository._from_puid)
    updater_date = datetime.fromisoformat(updater["updated_version"])

    # looking through the releases in reversed order to prevent wrongly updated formats
    for release in releases[::-1]:
        _date = release.find("release_date")

        if not _date or not _date.text:
            continue

        date = datetime.strptime(
            re.sub(r"(\d)(st|nd|rd|th)", r"\1", _date.text.strip()), "%d %B %Y"
        )

        if updater_date > date:
            continue

        formats = release.find_all("format")
        tasks = []

        for format in formats:
            puid_tag = format.find("puid")
            fmt_type = puid_tag.attrs.get("type")
            puid = f"{fmt_type}/{puid_tag.text.strip()}"

            # puids can appear in multiple release records
            if puid in handled_puids:
                continue

            tasks.append(lookup_puid(repository, puid))

        if tasks:
            await asyncio.gather(*tasks)

        logger.info(f"successfully updated to {_date.text.strip()}")

        # after we've handled all the formats for the current update
        # we must empty handled_puids, so if there is a newer update
        # of the format, it gets correctly updated.
        handled_puids.clear()

        # update repository and updater file, so if the user cancels
        # it doesn't go back to the start.
        repository.save()

        updater["last_updated"] = datetime.now()
        updater["updated_version"] = date
        updater_file.write_bytes(orjson.dumps(updater))

    after = len(repository._from_puid)
    logger.info(f"updated {after} formats, where {after - before} were new formats.")

    await service.session.close()
