from dataclasses import dataclass
from typing import Any
from xml.etree.ElementTree import Element

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pronom_cli import logger
from pronom_cli.models.action import ActionABC
from pronom_cli.utils import find_xml


@dataclass
class ByteSequence:
    name: str
    note: str
    offset: int
    max_offset: int
    position: str
    sequence: str


class Entry:
    COMPACT_DESCRIPTION_MAX_LEN = 80

    def __init__(self, source: str, puid: str) -> None:
        self.source = source
        self.puid = puid

        self.name = ""
        self.version = ""
        self.description = ""
        self.disclosure = ""

        self.family = ""
        self.types = ""

        self.created_date = ""
        self.created_by = ""
        self.last_updated_date = ""

        self.action: ActionABC | None = None

        self.extensions: list[str] = []
        self.sequences: list[ByteSequence] = []

    @property
    def is_aca(self) -> bool:
        return self.puid.startswith("aca-")

    @classmethod
    def from_xml(cls, puid: str, root: "Element[str]") -> "Entry":
        """
        Creates an instance of the Entry class by parsing data from an XML element.

        This class method initializes a Entry instance using the provided PUID
        (Pronom Unique Identifier) and data extracted from a given XML root element.
        The process involves extracting external signatures, byte sequences, format
        metadata (e.g., name, version, types, and description), and provenance details.

        Arguments:
            puid (str): The Pronom Unique Identifier for the entry.
            root (Element[str]): The root XML element from which information will be extracted.

        Returns:
            Entry: An initialized instance containing the data parsed from the XML.
        """
        c = cls("Pronom", puid)

        if signs := root.findall(".//{*}ExternalSignature"):
            for sign in signs:
                if (signature := sign.find("{*}Signature")) is None:
                    logger.warn("Signature not found")
                    continue

                c.extensions.append("." + signature.text)  # type: ignore

        if signs := root.findall(".//{*}ByteSequence"):
            for sign in signs:
                c.sequences.append(
                    ByteSequence(
                        find_xml(root, ".//{*}SignatureName"),
                        find_xml(root, ".//{*}SignatureNote"),
                        int(find_xml(sign, ".//{*}Offset", "0")),
                        int(find_xml(sign, ".//{*}MaxOffset", "0")),
                        find_xml(sign, ".//{*}PositionType"),
                        find_xml(sign, ".//{*}ByteSequenceValue"),
                    )
                )

        c.name = find_xml(root, ".//{*}FormatName")
        c.version = find_xml(root, ".//{*}FormatVersion")
        c.disclosure = find_xml(root, ".//{*}FormatDisclosure")
        c.description = find_xml(root, ".//{*}FormatDescription")
        c.types = find_xml(root, ".//{*}FormatTypes")
        c.family = find_xml(root, ".//{*}FormatFamilies")
        c.created_date = find_xml(root, ".//{*}ProvenanceSourceDate")
        c.last_updated_date = find_xml(root, ".//{*}LastUpdatedDate")
        c.created_by = find_xml(root, ".//{*}ProvenanceName")

        return c

    @classmethod
    def from_json(cls, puid: str, data: dict[str, Any]) -> "Entry":
        """
        Creates an instance of Entry from a JSON dictionary containing detailed
        information about the PRONOM format.

        Parameters:
            puid: str
                The PRONOM Unique Identifier for the format.
            data: dict[str, Any]
                A dictionary containing the format's metadata, such as its name,
                version, description, creation details, disclosure, format types,
                family, extensions, and associated byte sequences.

        Returns:
            Entry
                A fully initialized Entry object representing the specified
                PRONOM format.

        """
        c = cls("Pronom", puid)

        c.name = data["name"]
        c.version = data["version"]
        c.description = data["description"]
        c.created_date = data["created_date"]
        c.created_by = data["created_by"]
        c.last_updated_date = data["last_updated_date"]
        c.disclosure = data["disclosure"]
        c.types = data["types"]
        c.family = data["family"]
        c.extensions = data["extensions"]
        c.sequences = [ByteSequence(**seq) for seq in data["sequences"]]

        return c

    def print(self, detailed=False) -> None:
        console = Console()

        summary = Table(show_header=False, box=None, pad_edge=False)
        summary.add_column(style="bold cyan", no_wrap=True)
        summary.add_column(style="white")

        summary.add_row("PUID", self.puid or "-")
        summary.add_row("Name", self.name or "-")
        summary.add_row("Description", self.description or "-")
        summary.add_row("Version", self.version or "-")
        summary.add_row("Family", self.family or "-")
        summary.add_row("Created By", self.created_by or "-")
        summary.add_row("Types", self.types or "-")
        summary.add_row(
            "Extensions", ", ".join(self.extensions) if self.extensions else "-"
        )
        summary.add_row("Action", self.action.print() if self.action else "-")

        signature_table = Table(show_header=True)
        signature_table.add_column("Name", style="bold")
        signature_table.add_column("Note")
        signature_table.add_column("Position", style="cyan", no_wrap=True)
        signature_table.add_column("Offset", no_wrap=True)
        signature_table.add_column("Sequence", style="dim")

        if self.sequences:
            for sig in self.sequences:
                signature_table.add_row(
                    sig.name or "-",
                    sig.note or "-",
                    sig.position or "-",
                    f"{sig.offset}–{sig.max_offset}",
                    sig.sequence or "-",
                )
        else:
            signature_table.add_row("-", "-", "-", "-", "-")

        console.print(
            Panel(
                summary, title=f"{self.source.capitalize()} Entry", border_style="blue"
            )
        )

        if detailed:
            metadata = Table(show_header=False, box=None, pad_edge=False)
            metadata.add_column(style="bold cyan", no_wrap=True)
            metadata.add_column(style="white")
            metadata.add_row("Disclosure", self.disclosure or "-")
            metadata.add_row("Created Date", self.created_date or "-")
            metadata.add_row("Last Updated", self.last_updated_date or "-")
            console.print(Panel(metadata, title="Metadata", border_style="magenta"))
            console.print(
                Panel(signature_table, title="Byte Sequences", border_style="green")
            )

    @staticmethod
    def print_compact_list(entries: list["Entry"], detailed=False) -> None:
        console = Console()

        table = Table(show_header=True, leading=1)
        table.add_column("Source", style="white", no_wrap=True)
        table.add_column("PUID", style="bold cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Description", style="white", no_wrap=True)
        table.add_column("Extensions", style="white")
        table.add_column("Action", style="white")

        for entry in entries:
            action = entry.action.print().splitlines()[0] if entry.action else "-"
            description = entry.description.strip() if entry.description else "-"
            if len(description) > Entry.COMPACT_DESCRIPTION_MAX_LEN:
                description = (
                    description[: Entry.COMPACT_DESCRIPTION_MAX_LEN - 1].rstrip() + "…"
                )
            name = f"{entry.name}({entry.version})" if entry.version else entry.name
            table.add_row(
                entry.source,
                entry.puid or "-",
                name or "-",
                description,
                ", ".join(entry.extensions) if entry.extensions else "-",
                action,
            )

        console.print(table)
