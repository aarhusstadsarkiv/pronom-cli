from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pronom_cli.models.action import ActionABC


@dataclass
class ByteSequence:
    name: str
    note: str
    offset: int
    max_offset: int
    position: str
    sequence: str


@dataclass
class EntryABC(ABC):
    source: str
    name: str = ""
    version: str = ""
    types: str = ""
    description: str = ""
    created_by: str = ""
    extensions: list[str] = field(default_factory=list)
    sequences: list[ByteSequence] = field(default_factory=list)

    @property
    def action(self) -> ActionABC | None:
        return None

    @abstractmethod
    def print(self, detailed: bool = False) -> None:
        pass
