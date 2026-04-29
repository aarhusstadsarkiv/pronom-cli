from abc import ABC, abstractmethod
from typing import Any

from pronom_cli import logger
from pronom_cli.models.entry import Entry


class Repository(ABC):
    def __init__(self) -> None:
        self._from_puid: dict[str, Entry] = {}
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

    def add(self, key: str, value: Any) -> None:
        """
        Adds a key-value pair to the relevant internal storage based on the type of the value provided.

        If the value is a string, it associates the key with a list of formats it belongs to
        If the value is an instance of Entry, it creates a direct mapping between the
        key and the Entry object for easy retrieval.

        If an unsupported type is provided for the value, an error is logged.

        Parameters:
            key (str): The key to associate with the value. Typically represents extensions or PUIDs.
            value (str | Entry): The value to associate with the key. It can either be a string or
                an instance of Entry depending on the context.

        Returns:
            None
        """
        if isinstance(value, str):
            self.add_extension(key, value)
        elif isinstance(value, Entry):
            self._from_puid[key] = value

            # add necessary extensions from entry
            for ext in value.extensions:
                self.add(key, ext)
        else:
            logger.error(f"unknown value ({key}: type({type(value)}))")

    def exists(self, key: str) -> Any:
        return key in self._from_puid or key in self._from_extensions
