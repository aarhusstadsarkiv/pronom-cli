from pathlib import Path

import orjson
from bs4 import BeautifulSoup

from pronom_cli import service
from pronom_cli.models.simple import SimpleEntry
from pronom_cli.repository.base import Repository


class FileProInfoRepository(Repository[SimpleEntry]):
    URL = "https://fileproinfo.com/file-type/"

    def __init__(self) -> None:
        super().__init__()

        self.cache_dir = Path.home() / ".cache" / "pronom_cli"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def load(cls) -> "FileProInfoRepository":
        c = cls()

        cache_file = c.cache_dir / "fileproinfo.json"

        if not cache_file.exists():
            return c

        cache_obj = orjson.loads(cache_file.read_bytes())

        for key, obj in cache_obj.items():
            c.add(key, SimpleEntry(**obj))

        return c

    def save(self) -> None:
        cache_file = self.cache_dir / "fileproinfo.json"
        cache_file.write_bytes(orjson.dumps(self.from_identifiers))

    async def get_one(self, key: str) -> SimpleEntry | None:
        if key in self.from_extensions:
            return self.from_identifiers[self.from_extensions[key][0]]

        if key in self.from_identifiers:
            return self.from_identifiers[key]

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

        before_description = soup.find(
            "input", attrs={"id": "ContentPlaceHolder1_txtId"}
        )
        if not before_description:
            return

        description_tag = before_description.next_sibling.next_sibling  # type: ignore
        if not description_tag:
            return

        description = description_tag.text.strip()

        title_tag = soup.find("h2")
        if not title_tag:
            return

        title = title_tag.text.strip()

        information_section = soup.find_all("tr")

        created_by = ""
        types = ""

        for information in information_section:
            if not (row_key := information.find("td")):
                continue

            if row_key.has_attr("width"):
                continue

            if not (value := row_key.next_sibling.next_sibling):  # type: ignore
                continue

            _key = row_key.text.strip()

            if _key == "Developer":
                created_by = value.text.strip()
            elif _key == "Category":
                types = value.text.strip()

        entry = SimpleEntry(
            source="FileProInfo",
            name=title,
            description=description,
            created_by=created_by,
            extensions=["." + key],
            types=types,
        )

        self.add(entry.hexdigest(), entry)
        self.save()

        return entry

    async def get_many(self, key: str) -> list[SimpleEntry]:
        if entry := await self.get_one(key):
            return [entry]

        return []
