from dataclasses import dataclass

from pronom_cli.models.action import AccessAction, StatutoryAccess
from pronom_cli.models.base import EntryABC


@dataclass
class MasterFormatEntry(EntryABC):
    access: AccessAction | None = None
    statutory: StatutoryAccess | None = None

    source: str = "Fileformats-master"

    # MasterFormatEntry is never meant to be used other than for PronomEntry.
    def print(self, detailed=False) -> None:
        pass
