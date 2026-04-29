from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from fast_yaml import Loader, load

from pronom_cli import config, logger
from pronom_cli.models.action import parse_action
from pronom_cli.models.entry import ByteSequence, Entry
from pronom_cli.repository.base import Repository


def small_pronom_entry(puid: str, data: dict[str, Any]) -> Entry:
    entry = Entry("fileformats", puid)
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

        self.cache_dir = Path.home() / ".cache" / "pronom_cli"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_yaml(self, filename: str) -> Any:
        cache_file = self.cache_dir / f"{filename}.yml"

        if cache_file.exists():
            last_modified = datetime.fromtimestamp(cache_file.stat().st_mtime)
            since_modified = datetime.now() - last_modified

            # cached for a day, if exceeds, we check for any new
            # commits on the github repo. if update-cache flag is true
            # it should ignore cache and update it.
            if since_modified < timedelta(days=1) and not config.flags["update-cache"]:
                return load(cache_file.read_text(), Loader=Loader)

        resp = requests.get(self.GITHUB_REPO + filename)

        if resp.status_code != 200:
            logger.error(f"failed to fetch {filename} from github")
            return

        cache_file.write_text(resp.text)
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

            if not entry.is_aca:
                continue

            seq_from_yaml = search_custom_signatures(signatures_yaml, entry.puid)
            if not seq_from_yaml:
                continue

            name = seq_from_yaml["signature"]
            note = seq_from_yaml.get("description", "")

            for key, label in (("bof", "BOF"), ("eof", "EOF")):
                sequence = seq_from_yaml.get(key, "")

                if not sequence:
                    continue

                entry.sequences.append(
                    ByteSequence(
                        name=name,
                        note=note,
                        offset=0,
                        max_offset=0,
                        position=label,
                        sequence=sequence,
                    )
                )
        return c

    def get(self, key: str) -> Entry | list[Entry] | None:
        """
        Retrieves Entry or a list of Entry objects based on the provided key.

        If the provided key represents a file extension (i.e., it starts with a dot), the function
        returns a list of Entry objects corresponding to the file formats associated with that
        extension. If the extension does not exist in the data, the function returns None.

        If the key does not represent an extension, it is treated as a PUID, and the function returns
        a Entry object corresponding to the PUID if it exists, otherwise returns None.

        Parameters:
            key:
                A string representing a file extension (e.g., ".jpg") or a PUID.

        Returns:
            Entry | list[Entry] | None:
                A Entry object, a list of Entry objects, or None if the key is not found.
        """
        if key.startswith("."):
            if key not in self._from_extensions:
                return

            entries: list[Entry] = []
            # print(self._from_extensions)
            for format in self._from_extensions[key]:
                # print(self._from_extensions[key])
                entries.append(self._from_puid[format])
            return entries

        return self._from_puid.get(key, None)
