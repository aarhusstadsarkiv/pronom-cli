from bs4 import BeautifulSoup

from pronom_cli import service
from pronom_cli.models.simple import SimpleEntry
from pronom_cli.repository.base import Repository


class FilextRepository(Repository[SimpleEntry]):
    URL = "https://filext.com/file-extension/"

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    async def load(cls) -> "FilextRepository":
        return cls()

    async def get_one(self, key: str) -> SimpleEntry | None:
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

        return SimpleEntry(
            source="Filext",
            description=description,
            name=key.upper(),
            version="Generic",
            types=file_classification.text.strip(),
            created_by=created_by,
            extensions=["." + key],
        )

    async def get_many(self, key: str) -> list[SimpleEntry]:
        entry = await self.get_one(key)

        if not entry:
            return []

        return [entry]
