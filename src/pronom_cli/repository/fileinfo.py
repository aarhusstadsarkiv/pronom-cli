from typing import override

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pronom_cli.models.models import Extension, Format
from pronom_cli.repository.base import Repository


class FileInfoRepository(Repository):
    URL = "https://fileinfo.com/extension/"

    @override
    def get(
        self, db_session: Session, http_session: httpx.Client, key: str
    ) -> list[Format]:
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
        if key.startswith("."):
            key = key[1:]
        else:
            return []

        response = http_session.get(FileInfoRepository.URL + key)

        soup = BeautifulSoup(response.text, "html.parser")

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
            description += f" See {FileInfoRepository.URL + key} for more information."

            identifier = db_session.scalar(
                select(func.count(Format.id)).filter(Format.source == "Fileinfo")
            )
            assert identifier is not None

            identifier += 1

            entry = Format(
                source="Fileinfo",
                identifier=f"fileinfo/{identifier}",
                name=title.text.strip() if title else "",
                description=description,
                created_by=created_by.text.strip() if created_by else "",
                extensions=[Extension(extension="." + key)],
            )
            entries.append(entry)

            db_session.add(entry)

        return entries
