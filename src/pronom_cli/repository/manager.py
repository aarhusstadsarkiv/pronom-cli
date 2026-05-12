import asyncio
from typing import cast

from pronom_cli.models.base import EntryABC
from pronom_cli.models.pronom import PronomEntry
from pronom_cli.repository.base import Repository
from pronom_cli.repository.fileformats import FileFormatsRepository
from pronom_cli.repository.fileinfo import FileInfoRepository
from pronom_cli.repository.fileproinfo import FileProInfoRepository
from pronom_cli.repository.filext import FilextRepository
from pronom_cli.repository.masterformats import MasterFormatsRepository
from pronom_cli.repository.pronom import PronomRepository
from pronom_cli.utils import Filter, merge_unique


class RepositoryManager:
    def __init__(
        self,
        pronom: PronomRepository,
        fileformats: FileFormatsRepository,
        fileinfo: FileInfoRepository,
        filext: FilextRepository,
        masterformats: MasterFormatsRepository,
        fileproinfo: FileProInfoRepository,
        filters: list[Filter],
    ):
        self.pronom = pronom
        self.fileformats = fileformats
        self.fileinfo = fileinfo
        self.filext = filext
        self.fileproinfo = fileproinfo

        self._masterformats = masterformats

        self.filters = filters

    async def get_from_identifier(self, identifier: str) -> EntryABC | None:
        """
        Fetches a Entry object corresponding to a specific identifier.

        This method retrieves a Entry object from a set of different repositories.
        Priority is given to ACA-specific PUIDs, which are exclusively fetched from file formats.
        For non-ACA PUIDs, the PRONOM repository gets searched through first. If an entry is found,
        additional actions are appended to it before returning the entry.

        Parameters:
            identifier: str
                The identifier used to fetch the corresponding Entry.

        Returns:
            Entry | None:
                A Entry object corresponding to the specified identifier if it
                exists, or None if no matching entry is found.
        """
        if "fmt/" in identifier:
            # aca-formats only appear in fileformats
            is_aca_puid = identifier.startswith("aca")

            if is_aca_puid:
                return await self.fileformats.get_one(identifier)

            # we'll search through pronom first
            entry = await self.pronom.get_one(identifier)

            if not entry:
                return

            # append action if it exists
            await self._append_action_to_pronom(entry)
            await self._append_master_to_pronom(entry)

            return entry

        source = identifier.split("/")[0]
        repository = {
            "fmt": self.pronom,
            "aca-fmt": self.fileformats,
            "fileinfo": self.fileinfo,
            "filext": self.filext,
            "fileproinfo": self.fileproinfo,
        }.get(source)

        if not repository:
            return

        entry = await repository.get_one(identifier)

        if not entry:
            return

        if isinstance(entry, PronomEntry):
            await self._append_action_to_pronom(entry)
            await self._append_master_to_pronom(entry)

        return entry

    async def _append_action_to_pronom(self, entry: PronomEntry) -> None:
        """
        Adds action details to a Entry object if not already set.

        Parameters:
            entry (Entry):
                The Entry object to be updated.
        """
        if entry.from_fileformats:
            return

        entry.from_fileformats = await self.fileformats.get_one(entry.puid)

    async def _append_master_to_pronom(self, entry: PronomEntry) -> None:
        entry.from_masterformats = await self._masterformats.get_one(
            entry.puid
        ) or await self._masterformats.get_one(f"!{entry.types.lower()}")

    async def _empty_get_function(self) -> list:
        return []

    async def get_from_extension(self, ext: str, limit: int = 0) -> list[EntryABC]:
        """
        Retrieves and merges repositories information for the given extension.

        This method combines the information given from the different repositories,
        for the provided file extension. The merging process ensures that entries
        from the `pronom` source take precedence over those from the `fileformats`
        source in cases of conflict, while also avoiding duplicate entries.

        Parameters:
            ext (str): The file extension for which format information is to
            be retrieved.

        Returns:
            list[Entry]: A list of `Entry` objects representing
            the merged information, or a list from a single source if the
            other source lacks data for the specified extension.
        """

        def _fetch_from_repository(ext: str, repo: Repository, filter: Filter):
            return (
                repo.get_many(ext)
                if filter in self.filters
                else self._empty_get_function()
            )

        (
            from_pronom,
            from_fileformats,
            from_fileinfo,
            from_filext,
            from_fileproinfo,
        ) = await asyncio.gather(
            _fetch_from_repository(ext, self.pronom, Filter.PRONOM),
            _fetch_from_repository(ext, self.fileformats, Filter.FILEFORMATS),
            _fetch_from_repository(ext, self.fileinfo, Filter.FILEINFO),
            _fetch_from_repository(ext, self.filext, Filter.FILEXT),
            _fetch_from_repository(ext, self.fileproinfo, Filter.FILEPROINFO),
        )

        for entry in from_pronom:
            await self._append_action_to_pronom(entry)
            await self._append_master_to_pronom(entry)

        # since combining from_pronom and from_fileformats would
        # result in a bunch of collisions and overrides, we'll merge
        # them, where pronom wins in getting information over fileformats

        # from_pronom = [Pronom1, Pronom2]
        # from_fileformats = [SmallPronom2, SmallPronom3]
        # merged_results = [Pronom1, Pronom2, SmallPronom3]
        results = cast(
            list[EntryABC],
            merge_unique(from_pronom, from_fileformats, key=lambda entry: entry.puid)
            + from_fileinfo
            + from_filext
            + from_fileproinfo,
        )

        return results[:limit] if limit > 0 else results
