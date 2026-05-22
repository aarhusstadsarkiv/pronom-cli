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
    """Returns the Rich colour style for the given action name, defaulting to white."""
    return ACTION_COLORS.get(action_name, "white")


def print_row(label: str, value: str) -> None:
    """Prints a single label/value pair with consistent Rich styling."""
    console.print(
        f"[{LABEL_STYLE}]{label:<12}[/{LABEL_STYLE}] [{VALUE_STYLE}]{value}[/{VALUE_STYLE}]"
    )


def print_compact_list(entries: list["Format"]) -> None:
    """Renders a Rich table summarising a list of Format entries."""
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
    """Returns stripped text of the first matching XML element, or default if absent."""
    value = root.find(string)
    if value is None or value.text is None:
        return default

    text = value.text.strip()
    if not text:
        return default

    return text


def short_hexdigest(data: bytes) -> str:
    """Returns the first 6 characters of the MD5 hex digest of data."""
    hash_object = hashlib.md5(data)
    return hash_object.hexdigest()[:6]


def search_custom_signatures(
    data: list[dict[str, Any]], aca: str
) -> dict[str, Any] | None:
    """Returns the custom_signatures.yml entry for the given ACA PUID, or None if not found."""
    for row in data:
        puid = row["puid"]

        if aca == "aca-fmt/27" or not puid.startswith("aca"):
            continue

        if puid == aca:
            return row


class Filter(Enum):
    """Controls which external repositories are queried when looking up a format."""

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
    """Converts a list of Filter enum members to their lowercase name strings."""
    return [filter.name.lower() for filter in filters]
