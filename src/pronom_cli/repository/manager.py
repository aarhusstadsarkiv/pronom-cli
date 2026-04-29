from typing import Callable

from pronom_cli.models.entry import Entry
from pronom_cli.repository.fileformats import FileFormatsRepository
from pronom_cli.repository.pronom import PronomRepository


def _merge_unique(
    list_a: list[Entry],
    list_b: list[Entry],
    key: Callable[[Entry], object],
) -> list[Entry]:
    seen: dict[object, Entry] = {}
    for item in list_a + list_b:
        k = key(item)
        if k not in seen:
            seen[k] = item
    return list(seen.values())


class RepositoryManager:
    def __init__(self, pronom: PronomRepository, fileformats: FileFormatsRepository):
        self.pronom = pronom
        self.fileformats = fileformats

    def get_from_puid(self, puid: str) -> Entry | None:
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
            return self.fileformats.get(puid)

        # we'll search through pronom first
        entry: Entry = self.pronom.get(puid)
        if not entry:
            return

        # append action if it exists
        self._append_action_to_entry(entry)

        return entry

    def _append_action_to_entry(self, entry: Entry) -> None:
        """
        Adds action details to a Entry object if not already set.

        Parameters:
            entry (Entry):
                The Entry object to be updated.
        """
        if entry.action:
            return

        if self.fileformats.exists(entry.puid):
            small_entry: Entry = self.fileformats.get(entry.puid)
            entry.action = small_entry.action

    def get_from_extension(self, ext: str) -> list[Entry]:
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
        from_pronom = self.pronom.get(ext)
        from_fileformats = self.fileformats.get(ext)

        if not from_fileformats:
            return from_pronom

        if not from_pronom:
            return from_fileformats

        # since combining from_pronom and from_fileformats would
        # result in a bunch of collisions and overrides, we'll merge
        # them, where pronom wins in getting information over fileformats

        # from_pronom = [Pronom1, Pronom2]
        # from_fileformats = [SmallPronom2, SmallPronom3]
        # merged_results = [Pronom1, Pronom2, SmallPronom3]
        if from_pronom and from_fileformats:
            return _merge_unique(
                from_pronom, from_fileformats, key=lambda entry: entry.puid
            )

        # TODO: Extend extension search to other databases
        return []
