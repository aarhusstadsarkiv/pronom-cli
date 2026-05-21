import hashlib
from enum import Enum
from typing import TYPE_CHECKING, Any, Union
from xml.etree.ElementTree import Element, ElementTree

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from pronom_cli.models.models import Format

console = Console()

MAX_DESCRIPTION_WIDTH = 80
LABEL_STYLE = "dim"
VALUE_STYLE = "white"
PUID_STYLE = "bold cyan"
ACTION_COLORS: dict[str, str] = {
    "convert": "green",
    "extract": "green",
    "ignore": "dim",
    "manual": "yellow",
    "template": "dim",
}


def action_style(action_name: str) -> str:
    return ACTION_COLORS.get(action_name, "white")


def print_row(label: str, value: str) -> None:
    console.print(
        f"[{LABEL_STYLE}]{label:<12}[/{LABEL_STYLE}] [{VALUE_STYLE}]{value}[/{VALUE_STYLE}]"
    )


def print_compact_list(entries: list["Format"]) -> None:
    table = Table(show_header=True, leading=1)
    table.add_column("Source", style="white", no_wrap=True)
    table.add_column("Identifier", style="bold cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Description", style="white", no_wrap=True)
    table.add_column("Extensions", style="white")
    table.add_column("Action", style="white")

    for entry in entries:
        action_str = entry.action.action.splitlines()[0] if entry.action else "-"
        style = action_style(action_str)

        description = entry.description.strip() if entry.description else "-"
        if len(description) > MAX_DESCRIPTION_WIDTH:
            description = description[: MAX_DESCRIPTION_WIDTH - 1].rstrip() + "…"

        name = f"{entry.name} ({entry.version})" if entry.version else entry.name
        exts = (
            ", ".join(e.extension for e in entry.extensions)
            if entry.extensions
            else "-"
        )

        table.add_row(
            entry.source,
            entry.identifier,
            name or "-",
            description,
            exts,
            f"[{style}]{action_str}[/{style}]",
        )

    console.print(table)


def find_xml(
    root: Union["ElementTree[Element[str]]", "Element[str]"],
    string: str,
    default: str = "",
) -> str:
    """
    Finds a text value within the given XML element tree or element using the provided string query.

    Parameters:
        root: Union[ElementTree[Element[str]], Element[str]]
            The XML element tree or XML element to be searched.

        string: str
            The query string specifying the child element to search for.

        default: str, optional
            The default value to return if the queried element or its text is not found
            or if its text is empty. Defaults to an empty string.

    Returns:
        str:
            The stripped text content of the found element, or the default value if no
            valid content is found.
    """
    value = root.find(string)
    if value is None or value.text is None:
        return default

    text = value.text.strip()
    if not text:
        return default

    return text


def short_hexdigest(data: bytes) -> str:
    hash_object = hashlib.md5(data)
    return hash_object.hexdigest()[:6]


def search_custom_signatures(
    data: list[dict[str, Any]], aca: str
) -> dict[str, Any] | None:
    for row in data:
        puid = row["puid"]

        if aca == "aca-fmt/27" or not puid.startswith("aca"):
            continue

        if puid == aca:
            return row


class Filter(Enum):
    FILEINFO = "fileinfo"
    PRONOM = "pronom"
    FILEFORMATS = "fileformats"
    FILEXT = "filext"
    FILEPROINFO = "fileproinfo"

    def to_list(self) -> list["Filter"]:
        return [
            self.FILEINFO,
            self.PRONOM,
            self.FILEFORMATS,
            self.FILEXT,
            self.FILEPROINFO,
        ]


def filters_to_names(filters: list[Filter]) -> list[str]:
    return [filter.name.lower() for filter in filters]
