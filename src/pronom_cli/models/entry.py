from dataclasses import dataclass
from typing import Any, Union
from xml.etree.ElementTree import Element, ElementTree

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pronom_cli import config, logger
from pronom_cli.models.action import ActionABC


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

    def _find(
        self,
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
                        c._find(root, ".//{*}SignatureName"),
                        c._find(root, ".//{*}SignatureNote"),
                        int(c._find(sign, ".//{*}Offset", "0")),
                        int(c._find(sign, ".//{*}MaxOffset", "0")),
                        c._find(sign, ".//{*}PositionType"),
                        c._find(sign, ".//{*}ByteSequenceValue"),
                    )
                )

        c.name = c._find(root, ".//{*}FormatName")
        c.version = c._find(root, ".//{*}FormatVersion")
        c.disclosure = c._find(root, ".//{*}FormatDisclosure")
        c.description = c._find(root, ".//{*}FormatDescription")
        c.types = c._find(root, ".//{*}FormatTypes")
        c.family = c._find(root, ".//{*}FormatFamilies")
        c.created_date = c._find(root, ".//{*}ProvenanceSourceDate")
        c.last_updated_date = c._find(root, ".//{*}LastUpdatedDate")
        c.created_by = c._find(root, ".//{*}ProvenanceName")

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

    def print(self) -> None:
        console = Console()

        summary = Table(show_header=False, box=None, pad_edge=False)
        summary.add_column(style="bold cyan", no_wrap=True)
        summary.add_column(style="white")

        summary.add_row("PUID", self.puid)
        summary.add_row("Name", self.name or "-")
        summary.add_row("Description", self.description or "-")
        summary.add_row("Version", self.version or "-")
        summary.add_row("Family", self.family or "-")
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

        console.print(Panel(summary, title="PRONOM Entry", border_style="blue"))

        if config.flags["all"]:
            metadata = Table(show_header=False, box=None, pad_edge=False)
            metadata.add_column(style="bold cyan", no_wrap=True)
            metadata.add_column(style="white")
            metadata.add_row("Disclosure", self.disclosure or "-")
            metadata.add_row("Created Date", self.created_date or "-")
            metadata.add_row("Created By", self.created_by or "-")
            metadata.add_row("Last Updated", self.last_updated_date or "-")
            console.print(Panel(metadata, title="Metadata", border_style="magenta"))
            console.print(
                Panel(signature_table, title="Byte Sequences", border_style="green")
            )

    @staticmethod
    def print_compact_list(entries: list["Entry"]) -> None:
        console = Console()

        table = Table(show_header=True, leading=1)
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
            table.add_row(
                entry.puid,
                entry.name or "-",
                description,
                ", ".join(entry.extensions) if entry.extensions else "-",
                action,
            )

        console.print(table)
