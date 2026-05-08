from pathlib import Path

import orjson
from bs4 import BeautifulSoup

from pronom_cli import service
from pronom_cli.models.simple import SimpleEntry
from pronom_cli.repository.base import Repository


class FileInfoRepository(Repository[SimpleEntry]):
    URL = "https://fileinfo.com/extension/"

    def __init__(self) -> None:
        super().__init__()

        self.cache_dir = Path.home() / ".cache" / "pronom_cli"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def load(cls) -> "FileInfoRepository":
        c = cls()

        cache_file = c.cache_dir / "fileinfo.json"

        if not cache_file.exists():
            return c

        cache_obj = orjson.loads(cache_file.read_bytes())

        for key, obj in cache_obj.items():
            c.add(key, SimpleEntry(**obj))

        return c

    def save(self) -> None:
        cache_file = self.cache_dir / "fileinfo.json"
        cache_file.write_bytes(orjson.dumps(self.from_identifiers))

    async def get_one(self, key: str) -> SimpleEntry | None:
        """
        Retrieves a single entry based on the provided key.

        The method utilises the parsing done in `get_many(key)` and
        returns the first element in the list of entries.

        Parameters:
            key (str): The file extension to search for.

        Returns:
            Entry | None:
                Returns a first Entry object if the extension exists in the
                FileInfo database, otherwise None.
        """
        is_extension = key.startswith(".")

        if is_extension:
            if key not in self.from_extensions:
                entries = await self.get_many(key)
                return entries[0] if entries else None

            # get the first identifier from extension list and return format
            return self.from_identifiers[self.from_extensions[key][0]]

        return self.from_identifiers.get(key)

    async def get_many(self, key: str) -> list[SimpleEntry]:
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
            entries = []

            for identifier in self.from_extensions[key]:
                entries.append(self.from_identifiers[identifier])

            return entries

        if key.startswith("."):
            key = key[1:]
        else:
            return []

        response = await service.session.get(self.URL + key)

        soup = BeautifulSoup(await response.text(), "html.parser")

        # h1.pageheading is a big error message
        if soup.select_one("h1.pageheading"):
            return []

        formats = soup.find_all("div", attrs={"class": "filetype card hasfooter"})

        entries = []

        for format in formats:
            title = format.select_one("h2.title")
            header_info = format.select_one("table.headerInfo")
            created_by_tag = header_info.find("tr") if header_info else ""
            created_by = created_by_tag.find("td").next_sibling.next_sibling  # type: ignore
            info_section = format.select_one("div.infoBox")

            description = (
                " ".join([desc.text for desc in info_section.find_all("p")])
                if info_section
                else ""
            )
            description += f" See {self.URL + key} for more information."

            entry = SimpleEntry(
                source="Fileinfo",
                name=title.text.strip() if title else "",
                description=description,
                created_by=created_by.text.strip() if created_by else "",
                extensions=["." + key],
            )
            entries.append(entry)

            self.add(entry.hexdigest(), entry)

        self.save()

        return entries
