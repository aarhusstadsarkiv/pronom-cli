import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fast_yaml import Loader, load

from pronom_cli import logger, service
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

    async def _get_yaml(self, filename: str, update_cache: bool = False) -> Any:
        """
        Retrieve and parse a YAML resource from cache or GitHub.

        The method first checks a local cache file in ``~/.cache/pronom_cli``.
        If the cache exists and is newer than 24 hours, it is used unless
        ``update_cache`` is set to ``True``. Otherwise, the file is fetched from
        the latest release download endpoint and the cache is refreshed.

        Parameters:
            filename:
                Name of the YAML file to read (for example,
                ``fileformats.yml`` or ``custom_signatures.yml``).
            update_cache:
                If ``True``, bypasses the age check and forces a remote fetch.

        Returns:
            Any:
                Parsed YAML content when successful; ``None`` if the remote
                request fails.
        """
        cache_file = self.cache_dir / f"{filename}"

        if cache_file.exists():
            last_modified = datetime.fromtimestamp(cache_file.stat().st_mtime)
            since_modified = datetime.now() - last_modified

            # cached for a day, if exceeds, we check for any new
            # commits on the github repo. if update-cache flag is true
            # it should ignore cache and update it.
            if since_modified < timedelta(days=1) and not update_cache:
                return load(cache_file.read_text(), Loader=Loader)

        response = await service.session.get(self.GITHUB_REPO + filename)

        if response.status != 200:
            logger.error(f"failed to fetch {filename} from github")
            return

        content = await response.text()
        cache_file.write_text(content)
        return load(content, Loader=Loader)

    @classmethod
    async def load(cls, update_cache=False) -> "FileFormatsRepository":
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

        fileformats_yaml, signatures_yaml = await asyncio.gather(
            c._get_yaml(c.FILEFORMATS_FILE, update_cache),
            c._get_yaml(c.CUSTOM_SIGNATURES_FILE, update_cache),
        )

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

    async def get_one(self, key: str) -> Entry | None:
        """
        Retrieves a single Entry object based on the provided key.

        The method assumes that the provided key represents an PUID and fetches
        it from the PUID database.

        Parameters:
            key:
                A string representing a PUID (e.g., fmt/1).

        Returns:
            Entry | None:
                The entry associated with the PUID. If it doesn't exist, then None.
        """
        return self._from_puid.get(key)

    async def get_many(self, key: str) -> list[Entry]:
        """
        Retrieves a list of Entry objects based on the provided key.

        It assumes the provided key represents a file extension and retrieves a list of Entry
        objects corresponding to the file formats associated with that extension. If the extension
        does not exist in the data, the function returns None.

        Parameters:
            key:
                A string representing a file extension (e.g., ".jpg").

        Returns:
            list[Entry]:
                a list of Entry objects.
        """
        if key not in self._from_extensions:
            return []

        entries: list[Entry] = []

        for format in self._from_extensions[key]:
            entries.append(self._from_puid[format])

        return entries
