import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from pronom_cli import logger, service
from pronom_cli.models.entry import Entry
from pronom_cli.repository.base import Repository


class FilextRepository(Repository):
    URL = "https://filext.com/file-extension/"

    def __init__(self) -> None:
        super().__init__()

        self.regex = re.compile(r"^([^\n(]+?)\s*(?:\(([^)]+)\))?\s+by\s+([^\n]+)")

    @classmethod
    async def load(cls) -> "FilextRepository":
        return cls()

    async def get_one(self, key: str) -> Any:
        entries = await self.get_many(key)
        return entries[0] if entries else None

    def _to_entry(self, data: Tag) -> Entry | None:
        description = data.select_one("div.smalltext")

        if not description:
            logger.error("failed to parse filext description")
            return

        to_match = " ".join([s.text for s in description.previous_siblings]).strip()
        match = self.regex.match(to_match)

        if not match:
            logger.error("filext header part didn't match the regex")
            return

        developer, classification, name = match.groups()

        entry = Entry("filext", "")
        entry.name = name
        entry.types = classification
        entry.created_by = developer
        entry.description = description.text.strip()  # type: ignore
        return entry

    async def get_many(self, key: str) -> list[Entry]:
        """
        Retrieves a list of entries based on the provided key.

        The method assumes the provided key corresponds to an extension and
        sends a request to the corresponding FileInfo site, from which the
        HTML will be parsed with BeautifulSoup.

        Parameters:
            key (str): The file extension to search for.

        Returns:
            list[Entry]:
                Returns a list of Entry objects if the extension exists in the FileInfo database.
        """
        if key.startswith("."):
            key = key[1:]

        response = await service.session.get(
            self.URL + key,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
        )

        soup = BeautifulSoup(await response.text(), "html.parser")

        if not (info_header := soup.find("h2")):
            return []

        if not (main_application_info := info_header.next_sibling.next_sibling):  # type: ignore
            return []

        if not (alternatives := soup.find("ol", attrs={"class": "app"})):
            return []

        items = alternatives.find_all("li")

        if not (main_entry := self._to_entry(items[0])):
            return []

        main_entry.description = main_application_info.text

        entries: list[Entry] = [main_entry]

        for item in items[1:]:
            if not item or not item.text:
                continue

            if entry := self._to_entry(item):
                entries.append(entry)

        return entries
