from functools import lru_cache
from typing import Any

import requests
from fast_yaml import Loader, load

from pronom_cli import logger
from pronom_cli.models.action import parse_action
from pronom_cli.models.pronom import ByteSequence, PronomEntry
from pronom_cli.repository.base import Repository


def small_pronom_entry(puid: str, data: dict[str, Any]) -> PronomEntry:
    entry = PronomEntry(puid)
    entry.name = data["name"]
    entry.action = parse_action(data)
    entry.description = data.get("description", "")
    entry.extensions = data.get("extensions", [])

    return entry


def search_custom_signatures(
    data: list[dict[str, Any]], aca: str
) -> dict[str, Any] | None:
    for row in data:
        puid = row["puid"]

        if aca == "aca-fmt/27" or not puid.startswith("aca"):
            continue

        if puid == aca:
            return row


class FileFormatsRepository(Repository):
    GITHUB_REPO = (
        "https://github.com/aarhusstadsarkiv/reference-files/releases/latest/download/"
    )
    FILEFORMATS_FILE = "fileformats.yml"
    CUSTOM_SIGNATURES_FILE = "custom_signatures.yml"

    def __init__(self) -> None:
        super().__init__()

    @lru_cache
    def _get_yaml(self, filename: str) -> Any:
        resp = requests.get(self.GITHUB_REPO + filename)
        if resp.status_code != 200:
            logger.error(f"failed to fetch {filename} from github")
        return load(resp.text, Loader=Loader)

    @classmethod
    async def load(cls) -> "FileFormatsRepository":
        """
        Loads file format data into the FileFormatsRepository class.

        This method initializes an instance of the class and processes the
        file format data retrieved from a YAML file. It maps PRONOM unique
        identifiers (PUIDs) to their corresponding data and creates a reverse
        lookup for file extensions to associated PUIDs.

        Returns:
             An instance of `FileFormatsRepository` populated with file
            format mappings.
        """
        c = cls()

        fileformats_yaml: dict[str, Any] = c._get_yaml(c.FILEFORMATS_FILE)
        signatures_yaml: list[dict[str, Any]] = c._get_yaml(c.CUSTOM_SIGNATURES_FILE)

        for puid, data in fileformats_yaml.items():
            entry = small_pronom_entry(puid, data)
            c.add(puid, entry)

            # extensions = data.get("extensions", [])
            # for ext in extensions:
            #     c.add(puid, ext)

            if entry.is_aca:
                seq_from_yaml = search_custom_signatures(signatures_yaml, entry.puid)
                if not seq_from_yaml:
                    continue

                bof: str = seq_from_yaml.get("bof", "")
                eof: str = seq_from_yaml.get("eof", "")

                for sequence in (bof, eof):
                    if not sequence:
                        continue

                    is_bof = sequence[4:].startswith("^")

                    entry.sequences.append(
                        ByteSequence(
                            name=seq_from_yaml["signature"],
                            note=seq_from_yaml.get("description", ""),
                            offset=0,
                            max_offset=0,
                            position="BOF" if is_bof else "EOF",
                            sequence=sequence,
                        )
                    )
        return c

    def add(self, key: str, value: Any) -> None:
        if isinstance(value, str):
            self.add_extension(key, value)
        elif isinstance(value, PronomEntry):
            self._from_puid[key] = value

            # add necessary extensions from entry
            for ext in value.extensions:
                self.add(key, ext)
        else:
            logger.error(f"unknown value ({key}: type({type(value)}))")

    def get(self, key: str) -> PronomEntry | list[PronomEntry] | None:
        """
        Retrieves PronomEntry or a list of PronomEntry objects based on the provided key.

        If the provided key represents a file extension (i.e., it starts with a dot), the function
        returns a list of PronomEntry objects corresponding to the file formats associated with that
        extension. If the extension does not exist in the data, the function returns None.

        If the key does not represent an extension, it is treated as a PUID, and the function returns
        a PronomEntry object corresponding to the PUID if it exists, otherwise returns None.

        Parameters:
            key:
                A string representing a file extension (e.g., ".jpg") or a PUID.

        Returns:
            PronomEntry | list[PronomEntry] | None:
                A PronomEntry object, a list of PronomEntry objects, or None if the key is not found.
        """
        if key.startswith("."):
            if key not in self._from_extensions:
                return

            entries: list[PronomEntry] = []
            # print(self._from_extensions)
            for format in self._from_extensions[key]:
                # print(self._from_extensions[key])
                entries.append(self._from_puid[format])
            return entries

        return self._from_puid.get(key, None)
