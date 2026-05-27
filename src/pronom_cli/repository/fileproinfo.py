from typing import override

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pronom_cli.models.models import Extension, Format
from pronom_cli.repository.base import Repository


class FileProInfoRepository(Repository):
    URL = "https://fileproinfo.com/file-type/"

    @override
    def get(
        self, db_session: Session, http_session: httpx.Client, key: str
    ) -> list[Format]:
        if key.startswith("."):
            key = key[1:]

        response = http_session.get(
            FileProInfoRepository.URL + key,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
        )

        soup = BeautifulSoup(response.text, "html.parser")

        before_description = soup.find(
            "input", attrs={"id": "ContentPlaceHolder1_txtId"}
        )
        if not before_description:
            return []

        description_tag = before_description.next_sibling.next_sibling  # type: ignore
        if not description_tag:
            return []

        description = description_tag.text.strip()

        title_tag = soup.find("h2")
        if not title_tag:
            return []

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

        identifier = db_session.scalar(
            select(func.count(Format.id)).filter(Format.source == "FileProInfo")
        )
        assert identifier is not None

        identifier += 1

        entry = Format(
            source="FileProInfo",
            identifier=f"fileproinfo/{identifier}",
            name=title,
            description=description,
            created_by=created_by,
            classification=types,
            extensions=[Extension(extension="." + key)],
        )
        db_session.add(entry)

        return [entry]
