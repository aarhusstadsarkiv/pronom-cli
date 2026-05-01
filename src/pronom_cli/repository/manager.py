from pronom_cli.models.entry import Entry
from pronom_cli.repository.fileformats import FileFormatsRepository
from pronom_cli.repository.fileinfo import FileInfoRepository
from pronom_cli.repository.filext import FilextRepository
from pronom_cli.repository.pronom import PronomRepository
from pronom_cli.utils import Filter, merge_unique


class RepositoryManager:
    def __init__(
        self,
        pronom: PronomRepository,
        fileformats: FileFormatsRepository,
        fileinfo: FileInfoRepository,
        filext: FilextRepository,
        filters: list[Filter] | None = None,
    ):
        self.pronom = pronom
        self.fileformats = fileformats
        self.fileinfo = fileinfo
        self.filext = filext

        self.filters = filters or [
            Filter.FILEFORMATS,
            Filter.PRONOM,
            Filter.FILEINFO,
            Filter.FILEXT,
        ]

    async def get_from_puid(self, puid: str) -> Entry | None:
        """
        Fetches a Entry object corresponding to a specific PUID.

        This method retrieves a Entry object from a set of different repositories.
        Priority is given to ACA-specific PUIDs, which are exclusively fetched from file formats.
        For non-ACA PUIDs, the PRONOM repository gets searched through first. If an entry is found,
        additional actions are appended to it before returning the entry.

        Parameters:
            puid: str
                The PUID used to fetch the corresponding Entry.

        Returns:
            Entry | None:
                A Entry object corresponding to the specified PUID if it
                exists, or None if no matching entry is found.
        """
        # aca-formats only appear in fileformats
        is_aca_puid = puid.startswith("aca")

        if is_aca_puid:
            return await self.fileformats.get_one(puid)

        # we'll search through pronom first
        entry = await self.pronom.get_one(puid)
        if not entry:
            return

        # append action if it exists
        await self._append_action_to_entry(entry)

        return entry

    async def _append_action_to_entry(self, entry: Entry) -> None:
        """
        Adds action details to a Entry object if not already set.

        Parameters:
            entry (Entry):
                The Entry object to be updated.
        """
        if entry.action:
            return

        if small_entry := await self.fileformats.get_one(entry.puid):
            entry.action = small_entry.action

    async def get_from_extension(self, ext: str, limit: int = 0) -> list[Entry]:
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

        sources = {
            Filter.PRONOM: self.pronom,
            Filter.FILEFORMATS: self.fileformats,
            Filter.FILEINFO: self.fileinfo,
            Filter.FILEXT: self.filext,
        }

        results = {
            f: await source.get_many(ext)
            for f, source in sources.items()
            if f in self.filters
        }

        from_pronom = results.get(Filter.PRONOM, [])
        from_fileformats = results.get(Filter.FILEFORMATS, [])
        from_fileinfo = results.get(Filter.FILEINFO, [])
        from_filext = results.get(Filter.FILEXT, [])

        for entry in from_pronom:
            await self._append_action_to_entry(entry)

        # since combining from_pronom and from_fileformats would
        # result in a bunch of collisions and overrides, we'll merge
        # them, where pronom wins in getting information over fileformats

        # from_pronom = [Pronom1, Pronom2]
        # from_fileformats = [SmallPronom2, SmallPronom3]
        # merged_results = [Pronom1, Pronom2, SmallPronom3]
        results = (
            merge_unique(from_pronom, from_fileformats, key=lambda entry: entry.puid)
            + from_fileinfo
            + from_filext
        )

        return results[:limit] if limit > 0 else results
