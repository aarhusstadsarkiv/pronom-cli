import xml.etree.ElementTree as ET
from dataclasses import asdict
from typing import Any

import orjson
import requests
from bs4 import BeautifulSoup

from pronom_cli import config, logger
from pronom_cli.models.pronom import PronomEntry
from pronom_cli.repository.base import Repository


class PronomRepository(Repository):
    def __init__(self) -> None:
        super().__init__()

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
        data: dict[str, Any] = orjson.loads(config.REPO_FILE.read_bytes())
        c = cls()

        for key, value in data.items():
            if key.startswith("."):
                c._from_extensions[key] = value
            else:
                c._from_puid[key] = PronomEntry.from_json(key, value)

        return c

    def add(self, key: str, value: str | PronomEntry) -> None:
        """
        Adds a key-value pair to the relevant internal storage based on the type of the value provided.

        If the value is a string, it associates the key with a list of formats it belongs to
        If the value is an instance of PronomEntry, it creates a direct mapping between the
        key and the PronomEntry object for easy retrieval.

        If an unsupported type is provided for the value, an error is logged.

        Parameters:
            key (str): The key to associate with the value. Typically represents extensions or PUIDs.
            value (str | PronomEntry): The value to associate with the key. It can either be a string or
                an instance of PronomEntry depending on the context.

        Returns:
            None
        """
        if isinstance(value, str):
            self.add_extension(key, value)
        elif isinstance(value, PronomEntry):
            self._from_puid[key] = value

            # add necessary extensions from entry
            for ext in value.extensions:
                self.add(key, ext)
        else:
            logger.error(f"unknown value ({key}: type({type(value)}))")

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

        config.REPO_FILE.write_bytes(
            orjson.dumps(serialized_entries | self._from_extensions)
        )

    def get(self, key: str) -> PronomEntry | list[PronomEntry] | None:
        """
        Retrieves a Pronom entry or a list of Pronom entries based on the provided key.

        The method determines whether the provided key corresponds to a PUID
        and fetches the corresponding entry. If the key does not match a PUID
        pattern, it attempts to retrieve entries based on file extension.

        Parameters:
            key (str): The key to search for, which can be a PUID or file extension.

        Returns:
            PronomEntry | list[PronomEntry] | None:
                Returns a single PronomEntry if the key matches a PUID, a list of PronomEntry
                objects if the key matches file extensions, or None if no match is found.
        """
        is_puid = "fmt" in key.split("/")[0]

        if is_puid:
            return self._get_by_puid(key)

        return self._get_by_extension(key)

    def _get_from_pronom(self, puid: str, save: bool = True) -> PronomEntry | None:
        """
        Fetches and parses PRONOM entry data using the supplied PUID and optionally saves it.

        Sends HTTP requests to retrieve PRONOM entry details associated with the specified PUID
        from the UK's National Archives website. Parses the response and uses it to create a
        PronomEntry object. The entry can be optionally stored and persisted for later use.

        Parameters:
            puid: str
                The PRONOM unique identifier (PUID) for the file format.
            save: bool, default True
                Indicates whether the PronomEntry should be persisted after being created.

        Returns:
            PronomEntry | None:
                A PronomEntry object representing the file format's metadata if the operation
                is successful, or None if the retrieval or parsing fails for any reason.
        """
        request = requests.get("http://www.nationalarchives.gov.uk/PRONOM/" + puid)
        soup = BeautifulSoup(request.text, "html.parser")

        form = soup.find(id="frmSaveAs")
        format_id_input = form.find("input", attrs={"name": "strFileFormatID"})  # type: ignore
        format_id = format_id_input.get("value") if format_id_input else None  # type: ignore

        response = requests.post(
            "https://www.nationalarchives.gov.uk/PRONOM/Format/proFormatDetailListAction.aspx",
            data={"strAction": "Save As XML", "strFileFormatID": format_id},
        )

        if response.status_code != 200:
            return

        if "The following errors were reported:" in response.text:
            return

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            logger.error("failed to parse response from pronom. maybe ratelimiting?")
            return

        entry = PronomEntry.from_xml(puid, root)
        self.add(puid, entry)

        if save:
            self.save()

        return entry

    def _get_by_puid(self, puid: str) -> PronomEntry | None:
        """
        Retrieves a PronomEntry object based on the provided PUID.

        If the PUID is not found in the local repository, a lookup will be
        performed in the official PRONOM database. If found, the entry is saved
        locally and returned.

        Parameters:
            puid (str):
                The Persistent Unique Identifier (PUID) that uniquely
                identifies a format in the PRONOM database.

        Returns:
            PronomEntry | None:
                A PronomEntry object if the PUID is found either locally
                or in the PRONOM database. None is returned if
                the entry does not exist in either source.
        """
        if puid not in self._from_puid:
            logger.warn(f"{puid} not found in the local repository, checking pronom...")

            entry = self._get_from_pronom(puid)

            if not entry:
                logger.error(f"{puid} doesn't exist in the official pronom database")
                return

            logger.info(f"found {puid} in the pronom database and saved locally.")
            return entry

        entry = self._from_puid[puid]
        return entry

    def _get_by_extension(self, ext: str) -> list[PronomEntry]:
        """
        Retrieves entries associated with a specific file extension from the local repository.

        This method searches for entries in the local repository that are linked to the
        specified file extension.

        Parameters:
            ext: str
                The file extension used to filter entries.

        Returns:
            list[PronomEntry]
                A list of `PronomEntry` objects associated with the given file extension.
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
