from pathlib import Path
from typing import override

import orjson
from bs4 import BeautifulSoup

from pronom_cli import service
from pronom_cli.models.old.simple import SimpleEntry
from pronom_cli.repository.base import Repository


class FilextRepository(Repository[SimpleEntry]):
    URL = "https://filext.com/file-extension/"

    def __init__(self) -> None:
        super().__init__()

        self.cache_dir = Path.home() / ".cache" / "pronom_cli"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # @classmethod
    # @override
    # async def load(cls) -> "FilextRepository":
    #     c = cls()

    #     cache_file = c.cache_dir / "filext.json"

    #     if not cache_file.exists():
    #         return c

    #     cache_obj = orjson.loads(cache_file.read_bytes())

    #     for key, obj in cache_obj.items():
    #         c.add(key, SimpleEntry(**obj))

    #     return c

    def save(self) -> None:
        cache_file = self.cache_dir / "filext.json"
        cache_file.write_bytes(orjson.dumps(self.from_identifiers))

    @override
    def get_one(self, key: str) -> SimpleEntry | None:
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
        if key in self.from_extensions:
            return self.from_identifiers[self.from_extensions[key][0]]

        if key in self.from_identifiers:
            return self.from_identifiers[key]

        if key.startswith("."):
            key = key[1:]

        response = service.session.get(
            self.URL + key,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
        )

        soup = BeautifulSoup(response.text, "html.parser")

        child = soup.select_one("span.redline")

        if not child or (child and not child.parent):
            return

        description = child.parent.text  # type: ignore

        introduction = description.split(". ")[0]
        splitted = introduction.split(" ")
        created_by = splitted[-1]

        technical_section = soup.find("div", attrs={"id": "technical-data"})

        if not technical_section:
            return

        file_classification = technical_section.find(
            "div", attrs={"class": "td halfbr"}
        )
        if not file_classification:
            return

        entry = SimpleEntry(
            source="Filext",
            description=description,
            name=key.upper(),
            types=file_classification.text.strip(),
            created_by=created_by,
            extensions=["." + key],
        )

        self.add(entry.hexdigest(), entry)
        self.save()

        return entry

    @override
    def get_many(self, key: str) -> list[SimpleEntry]:
        entry = self.get_one(key)

        if not entry:
            return []

        return [entry]
