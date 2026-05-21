from pathlib import Path
from typing import override

from pronom_cli import logger
from pronom_cli.models.old.pronom import PronomEntry
from pronom_cli.repository.base import Repository


class PronomRepository(Repository[PronomEntry]):
    def __init__(self) -> None:
        super().__init__()

        self.repo_file = Path(__file__).parent.parent / "repo.json"

    # @classmethod
    # @override
    # async def load(cls) -> "PronomRepository":
    #     """
    #     Initializes and loads a PronomRepository instance from a locally stored repository.
    #     Extensions and PRONOM entries are categorized and stored in the repository
    #     based on their respective keys in the parsed data.

    #     Returns:
    #         PronomRepository: An instance of PronomRepository populated with data from the
    #         repository file.

    #     """
    #     c = cls()
    #     data: dict[str, Any] = orjson.loads(c.repo_file.read_bytes())

    #     for key, value in data.items():
    #         if key.startswith("."):
    #             c.from_extensions[key] = value
    #         else:
    #             c.from_identifiers[key] = PronomEntry.from_json(key, value)

    #     return c

    # def save(self) -> None:
    #     """
    #     Serializes and saves the current state to the locally stored repository file.
    #     """
    #     serialized_entries = {
    #         puid: {
    #             "name": entry.name,
    #             "version": entry.version,
    #             "description": entry.description,
    #             "created_date": entry.created_date,
    #             "created_by": entry.created_by,
    #             "last_updated_date": entry.last_updated_date,
    #             "disclosure": entry.disclosure,
    #             "types": entry.types,
    #             "family": entry.family,
    #             "extensions": entry.extensions,
    #             "sequences": [asdict(seq) for seq in entry.sequences],
    #         }
    #         for puid, entry in self.from_identifiers.items()
    #     }

    #     self.repo_file.write_bytes(
    #         orjson.dumps(serialized_entries | self.from_extensions)
    #     )

    @override
    def get_one(self, key: str) -> PronomEntry | None:
        """
        Retrieves a single Pronom Entry based on the provided key.

        The method assumes the provided key corresponds to a PUID
        and fetches the entry that matches the provided PUID.

        Parameters:
            key (str): The key to search for, which can be a PUID or file extension.

        Returns:
            Entry | None:
                Returns a single Entry if the key matches a PUID or None if no match is found.
        """

        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    f.*, GROUP_CONCAT(e.extensions, ',') 
                FROM formats f
                LEFT JOIN extensions e 
                    ON e.entry_id = f.id
                WHERE f.identifier = ? AND f.source = 'PRONOM'
                GROUP BY f.id;
                """,
                (key),
            )
            row = cursor.fetchone()

        if not row:
            return self._get_from_pronom(key)

        return self._get_by_puid(key)

    @override
    def get_many(self, key: str) -> list[PronomEntry]:
        """
        Retrieves a list of Pronom entries based on the provided key.

        The method assumes the provided key corresponds to an extension and
        fetches the entries, which the extension points to.

        Parameters:
            key (str): The key to search for, which can be a PUID or file extension.

        Returns:
            list[Entry]:
                Returns a list of Entry objects if the key matches file extensions.
        """
        return self._get_by_extension(key)

    def _get_by_puid(self, puid: str) -> PronomEntry | None:
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
        if puid not in self.from_identifiers:
            logger.warn(f"{puid} not found in the local repository, checking pronom...")

            entry = self._get_from_pronom(puid)

            if not entry:
                logger.error(f"{puid} doesn't exist in the official pronom database")
                return

            logger.info(f"found {puid} in the pronom database and saved locally.")
            return entry

        entry = self.from_identifiers[puid]
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
            list[Entry]
                A list of `Entry` objects associated with the given file extension.
                If the extension is not found, an empty list is returned.
        """
        if ext not in self.from_extensions:
            logger.error(
                f"extension {ext} couldn't be found in the local repository, consider running `update`."
            )
            return []

        entries = []
        formats = self.from_extensions[ext]

        for format in formats:
            entries.append(self.from_identifiers[format])

        return entries
