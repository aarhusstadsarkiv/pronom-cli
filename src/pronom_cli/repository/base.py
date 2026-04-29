from abc import ABC, abstractmethod
from typing import Any

from pronom_cli.models.pronom import PronomEntry


class Repository(ABC):
    def __init__(self) -> None:
        self._from_puid: dict[str, PronomEntry] = {}
        self._from_extensions: dict[str, list[str]] = {}

    def add_extension(self, key: str, value: str) -> None:
        if value not in self._from_extensions:
            self._from_extensions[value] = [key]
        else:
            formats: list[str] = self._from_extensions[value]

            if key not in formats:
                formats.append(key)

    @classmethod
    @abstractmethod
    async def load(cls) -> "Repository":
        pass

    @abstractmethod
    def get(self, key: str) -> Any:
        pass

    @abstractmethod
    def add(self, key: str, value: Any) -> None:
        pass

    def exists(self, key: str) -> Any:
        return key in self._from_puid or key in self._from_extensions
