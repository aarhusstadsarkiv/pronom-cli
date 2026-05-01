from bs4 import BeautifulSoup

from pronom_cli import service
from pronom_cli.models.entry import Entry
from pronom_cli.repository.base import Repository


class FileInfoRepository(Repository):
    URL = "https://fileinfo.com/extension/"

    @classmethod
    async def load(cls) -> "FileInfoRepository":
        return cls()

    async def get_one(self, key: str) -> Entry | None:
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
        entries = await self.get_many(key)
        return entries[0] if entries else None

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
