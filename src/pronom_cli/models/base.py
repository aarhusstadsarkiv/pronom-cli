from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import orjson

from pronom_cli.models.action import ActionABC
from pronom_cli.utils import short_hexdigest


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
    identifier: str = ""
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

    def hexdigest(self) -> str:
        hash_value = short_hexdigest(orjson.dumps(self))
        return f"{self.source.lower()}/{hash_value}"
