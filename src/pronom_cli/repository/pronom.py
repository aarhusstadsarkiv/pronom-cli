import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any

import orjson
from bs4 import BeautifulSoup

from pronom_cli import config, logger
from pronom_cli.models.entry import Entry
from pronom_cli.repository.base import Repository


class PronomRepository(Repository):
    def __init__(self) -> None:
        super().__init__()

        self.repo_file = Path(__file__).parent.parent / "repo.json"

    @classmethod
    async def load(cls) -> "PronomRepository":
        """
        Initializes and loads a PronomRepository instance from a locally stored repository.
        Extensions and PRONOM entries are categorized and stored in the repository
        based on their respective keys in the parsed data.

        Returns:
            PronomRepository: An instance of PronomRepository populated with data from the
            repository file.

        """
        c = cls()
        data: dict[str, Any] = orjson.loads(c.repo_file.read_bytes())

        for key, value in data.items():
            if key.startswith("."):
                c._from_extensions[key] = value
            else:
                c._from_puid[key] = Entry.from_json(key, value)

        return c

    def save(self) -> None:
        """
        Serializes and saves the current state to the locally stored repository file.
        """
        serialized_entries = {
            puid: {
                "name": entry.name,
                "version": entry.version,
                "description": entry.description,
                "created_date": entry.created_date,
                "created_by": entry.created_by,
                "last_updated_date": entry.last_updated_date,
                "disclosure": entry.disclosure,
                "types": entry.types,
                "family": entry.family,
                "extensions": entry.extensions,
                "sequences": [asdict(seq) for seq in entry.sequences],
            }
            for puid, entry in self._from_puid.items()
        }

        self.repo_file.write_bytes(
            orjson.dumps(serialized_entries | self._from_extensions)
        )

    async def get(self, key: str) -> Entry | list[Entry] | None:
        """
        Retrieves a Pronom entry or a list of Pronom entries based on the provided key.

        The method determines whether the provided key corresponds to a PUID
        and fetches the corresponding entry. If the key does not match a PUID
        pattern, it attempts to retrieve entries based on file extension.

        Parameters:
            key (str): The key to search for, which can be a PUID or file extension.

        Returns:
            Entry | list[Entry] | None:
                Returns a single Entry if the key matches a PUID, a list of Entry
                objects if the key matches file extensions, or None if no match is found.
        """
        is_puid = "fmt" in key.split("/")[0]

        if is_puid:
            return await self._get_by_puid(key)

        return self._get_by_extension(key)

    async def _get_from_pronom(self, puid: str, save: bool = True) -> Entry | None:
        """
        Fetches and parses PRONOM entry data using the supplied PUID and optionally saves it.

        Sends HTTP requests to retrieve PRONOM entry details associated with the specified PUID
        from the UK's National Archives website. Parses the response and uses it to create a
        Entry object. The entry can be optionally stored and persisted for later use.

        Parameters:
            puid: str
                The PRONOM unique identifier (PUID) for the file format.
            save: bool, default True
                Indicates whether the Entry should be persisted after being created.

        Returns:
            Entry | None:
                A Entry object representing the file format's metadata if the operation
                is successful, or None if the retrieval or parsing fails for any reason.
        """
        pronom_response = await config.session.get(
            "http://www.nationalarchives.gov.uk/PRONOM/" + puid
        )

        soup = BeautifulSoup(await pronom_response.text(), "html.parser")

        form = soup.find(id="frmSaveAs")

        if not form:
            return

        format_id_input = form.find("input", attrs={"name": "strFileFormatID"})
        format_id = format_id_input.get("value") if format_id_input else None

        response = await config.session.get(
            "https://www.nationalarchives.gov.uk/PRONOM/Format/proFormatDetailListAction.aspx",
            data={"strAction": "Save As XML", "strFileFormatID": format_id},
        )

        if response.status != 200:
            return

        content = await response.text()

        if "The following errors were reported:" in content:
            return

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.error("failed to parse response from pronom. maybe ratelimiting?")
            return

        entry = Entry.from_xml(puid, root)
        self.add(puid, entry)

        if save:
            self.save()

        return entry

    async def _get_by_puid(self, puid: str) -> Entry | None:
        """
        Retrieves a Entry object based on the provided PUID.

        If the PUID is not found in the local repository, a lookup will be
        performed in the official PRONOM database. If found, the entry is saved
        locally and returned.

        Parameters:
            puid (str):
                The Persistent Unique Identifier (PUID) that uniquely
                identifies a format in the PRONOM database.

        Returns:
            Entry | None:
                A Entry object if the PUID is found either locally
                or in the PRONOM database. None is returned if
                the entry does not exist in either source.
        """
        if puid not in self._from_puid:
            logger.warn(f"{puid} not found in the local repository, checking pronom...")

            entry = await self._get_from_pronom(puid)

            if not entry:
                logger.error(f"{puid} doesn't exist in the official pronom database")
                return

            logger.info(f"found {puid} in the pronom database and saved locally.")
            return entry

        entry = self._from_puid[puid]
        return entry

    def _get_by_extension(self, ext: str) -> list[Entry]:
        """
        Retrieves entries associated with a specific file extension from the local repository.

        This method searches for entries in the local repository that are linked to the
        specified file extension.

        Parameters:
            ext: str
                The file extension used to filter entries.

        Returns:
            list[Entry]
                A list of `Entry` objects associated with the given file extension.
                If the extension is not found, an empty list is returned.
        """
        if ext not in self._from_extensions:
            logger.error(
                f"extension {ext} couldn't be found in the local repository, consider running `update`."
            )
            return []

        entries = []
        formats = self._from_extensions[ext]

        for format in formats:
            entries.append(self._from_puid[format])

        return entries
