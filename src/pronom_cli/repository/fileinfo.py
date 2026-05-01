from bs4 import BeautifulSoup

from pronom_cli import config
from pronom_cli.models.entry import Entry
from pronom_cli.repository.base import Repository


class FileInfoRepository(Repository):
    URL = "https://fileinfo.com/extension/"

    @classmethod
    async def load(cls) -> "FileInfoRepository":
        return FileInfoRepository()

    async def get(self, key: str) -> list[Entry]:
        if key.startswith("."):
            key = key[1:]

        response = await config.session.get(self.URL + key)

        soup = BeautifulSoup(await response.text(), "html.parser")

        # h1.pageheading is a big error message
        if soup.select_one("h1.pageheading"):
            return []

        formats = soup.find_all("div", attrs={"class": "filetype card hasfooter"})

        entries = []

        for format in formats:
            title = format.select_one("h2.title")
            header_info = format.select_one("table.headerInfo")
            created_by = header_info.find("tr") if header_info else ""
            info_section = format.select_one("div.infoBox")

            description = (
                " ".join([desc.text for desc in info_section.find_all("p")])
                if info_section
                else ""
            )
            description += f" See more on {self.URL + key} for more information."

            entry = Entry("fileinfo", "")
            entry.name = title.text if title else ""
            entry.description = description
            entry.created_by = created_by.text if created_by else ""
            entries.append(entry)

        return entries
