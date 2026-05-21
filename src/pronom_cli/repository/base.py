from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pronom_cli.models.old.base import EntryABC

T = TypeVar("T", bound=EntryABC)


class Repository(ABC, Generic[T]):
    # def __init__(self) -> None:
    #     self.conn = get_conn()

    # def _add_extension(self, key: str, value: str) -> None:
    #     if value not in self.from_extensions:
    #         self.from_extensions[value] = [key]
    #     else:
    #         formats: list[str] = self.from_extensions[value]

    #         if key not in formats:
    #             formats.append(key)

    # @classmethod
    # @abstractmethod
    # async def load(cls) -> "Repository":
    #     pass

    @abstractmethod
    def get_one(self, key: str) -> T | None:
        pass

    @abstractmethod
    def get_many(self, key: str) -> list[T]:
        pass

    # def add(self, key: str, value: T | str) -> None:
    #     """
    #     Adds a key-value pair to the relevant internal storage based on the type of the value provided.

    #     If the value is a string, it associates the key with a list of formats it belongs to
    #     If the value is an instance of Entry, it creates a direct mapping between the
    #     key and the Entry object for easy retrieval.

    #     If an unsupported type is provided for the value, an error is logged.

    #     Parameters:
    #         key (str): The key to associate with the value. Typically represents extensions or PUIDs.
    #         value (str | Entry): The value to associate with the key. It can either be a string or
    #             an instance of Entry depending on the context.

    #     Returns:
    #         None
    #     """
    #     if isinstance(value, str):
    #         self._add_extension(key, value)
    #     elif isinstance(value, EntryABC):
    #         self.from_identifiers[key] = value

    #         # add necessary extensions from entry
    #         for ext in value.extensions:
    #             self.add(key, ext)
    #     else:
    #         logger.error(f"unknown value ({key}: type({type(value)}))")
