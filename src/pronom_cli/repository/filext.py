from typing import override

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pronom_cli.models.models import Extension, Format
from pronom_cli.repository.base import Repository


class FilextRepository(Repository):
    URL = "https://filext.com/file-extension/"

    @override
    def get(
        self, db_session: Session, http_session: httpx.Client, key: str
    ) -> list[Format]:
        """Scrapes filext.com and returns Format entries for the given extension."""
        if key.startswith("."):
            key = key[1:]

        response = http_session.get(
            FilextRepository.URL + key,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        )

        soup = BeautifulSoup(response.text, "html.parser")
        child = soup.select_one("span.redline")

        if not child or (child and not child.parent):
            return []

        description = child.parent.text  # type: ignore

        introduction = description.split(". ")[0]
        splitted = introduction.split(" ")
        created_by = splitted[-1]

        technical_section = soup.find("div", attrs={"id": "technical-data"})
        if not technical_section:
            return []

        file_classification = technical_section.find(
            "div", attrs={"class": "td halfbr"}
        )
        if not file_classification:
            return []

        identifier = db_session.scalar(
            select(func.count(Format.id)).filter(Format.source == "Filext")
        )
        assert identifier is not None

        identifier += 1

        entry = Format(
            source="Filext",
            identifier=f"filext/{identifier}",
            description=description,
            name=key.upper(),
            classification=file_classification.text.strip(),
            created_by=created_by,
            extensions=[Extension(extension="." + key)],
        )
        db_session.add(entry)

        return [entry]
