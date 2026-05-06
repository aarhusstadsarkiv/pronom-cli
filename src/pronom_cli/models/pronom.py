from dataclasses import dataclass
from typing import Any
from xml.etree.ElementTree import Element

from pronom_cli import logger
from pronom_cli.models.action import ActionABC
from pronom_cli.models.base import ByteSequence, EntryABC
from pronom_cli.models.fileformats import FileFormatsEntry
from pronom_cli.models.master import MasterFormatEntry
from pronom_cli.utils import (
    LABEL_STYLE,
    PUID_STYLE,
    VALUE_STYLE,
    action_style,
    console,
    find_xml,
    print_row,
)


@dataclass
class PronomEntry(EntryABC):
    puid: str = ""
    disclosure: str = ""
    family: str = ""
    created_date: str = ""
    last_updated_date: str = ""

    from_fileformats: FileFormatsEntry | None = None
    from_masterformats: MasterFormatEntry | None = None

    source: str = "Pronom"

    @property
    def action(self) -> ActionABC | None:
        return self.from_fileformats.action if self.from_fileformats else None

    @classmethod
    def from_xml(cls, puid: str, root: "Element[str]") -> "PronomEntry":
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
        extensions = []

        if signs := root.findall(".//{*}ExternalSignature"):
            for sign in signs:
                if (signature := sign.find("{*}Signature")) is None:
                    logger.warn("Signature not found")
                    continue

                extensions.append("." + signature.text)  # type: ignore

        sequences = []

        if signs := root.findall(".//{*}ByteSequence"):
            for sign in signs:
                sequences.append(
                    ByteSequence(
                        find_xml(root, ".//{*}SignatureName"),
                        find_xml(root, ".//{*}SignatureNote"),
                        int(find_xml(sign, ".//{*}Offset", "0")),
                        int(find_xml(sign, ".//{*}MaxOffset", "0")),
                        find_xml(sign, ".//{*}PositionType"),
                        find_xml(sign, ".//{*}ByteSequenceValue"),
                    )
                )

        return cls(
            puid=puid,
            name=find_xml(root, ".//{*}FormatName"),
            version=find_xml(root, ".//{*}FormatVersion"),
            description=find_xml(root, ".//{*}FormatDescription"),
            created_by=find_xml(root, ".//{*}ProvenanceName"),
            created_date=find_xml(root, ".//{*}ProvenanceSourceDate"),
            last_updated_date=find_xml(root, ".//{*}LastUpdatedDate"),
            types=find_xml(root, ".//{*}FormatTypes"),
            family=find_xml(root, ".//{*}FormatFamilies"),
            disclosure=find_xml(root, ".//{*}FormatDisclosure"),
            extensions=extensions,
            sequences=sequences,
        )

    @classmethod
    def from_json(cls, puid: str, data: dict[str, Any]) -> "PronomEntry":
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
        return cls(
            puid=puid,
            name=data["name"],
            version=data["version"],
            description=data["description"],
            created_date=data["created_date"],
            created_by=data["created_by"],
            last_updated_date=data["last_updated_date"],
            disclosure=data["disclosure"],
            types=data["types"],
            family=data["family"],
            extensions=data["extensions"],
            sequences=[ByteSequence(**seq) for seq in data["sequences"]],
        )

    def print(self, detailed=False) -> None:
        console.print(
            f"[{PUID_STYLE}]{self.puid or '-'}[/{PUID_STYLE}]"
            f"  [{VALUE_STYLE}]{self.name or '-'}[/{VALUE_STYLE}]"
            + (f"  [dim]({self.version})[/dim]" if self.version else "")
        )
        console.print()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
            console.print()

        print_row("family", self.family or "-")
        print_row("created by", self.created_by or "-")
        print_row("types", self.types or "-")
        print_row("extensions", "  ".join(self.extensions) if self.extensions else "-")

        seq_count = len(self.sequences)
        print_row(
            "sequences", f"{seq_count} byte sequence{'s' if seq_count != 1 else ''}"
        )

        # Extra metadata + byte sequences only when detailed
        if detailed:
            console.print()
            print_row("disclosure", self.disclosure or "-")
            print_row("created", self.created_date or "-")
            print_row("updated", self.last_updated_date or "-")

            if self.sequences:
                console.print()
                console.print(f"[{LABEL_STYLE}]sequences[/{LABEL_STYLE}]")
                for i, sig in enumerate(self.sequences):
                    console.print(
                        f"[dim]  {'name':<10}[/dim] [{VALUE_STYLE}]{sig.name or '-'}[/{VALUE_STYLE}]"
                    )
                    console.print(
                        f"[dim]  {'position':<10}[/dim] [{VALUE_STYLE}]{sig.position or '-'}"
                        f"  offset {sig.offset}–{sig.max_offset}[/{VALUE_STYLE}]"
                    )
                    console.print(
                        f"[dim]  {'sequence':<10}[/dim] [cyan]{sig.sequence or '-'}[/cyan]"
                    )
                    if i < len(self.sequences) - 1:
                        console.print()

        # Action: first line gets a color, sub-lines (detail bullets) stay dim
        if self.from_fileformats and self.from_fileformats.action:
            console.print()
            console.print(
                "[white][bold]record was also found in fileformats[/bold][/white]"
            )

            access = self.from_fileformats.action

            action_lines = access.print().splitlines()
            statutory_name = action_lines[0]
            style = action_style(statutory_name)
            print_row("description", self.from_fileformats.description or "-")

            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [{style}]{statutory_name}[/{style}]"
            )
            for line in action_lines[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")

        if self.from_masterformats:
            console.print()
            console.print(
                "[white][bold]classification was also found in fileformats-master[/bold][/white]"
            )

            access = self.from_masterformats.access

            if not access:
                return

            action_lines = access.print().splitlines()
            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [white]access[/white]"
            )
            for line in action_lines[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")

            console.print()

            statutory = self.from_masterformats.statutory

            if not statutory:
                return

            statutory_lines = statutory.print().splitlines()
            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [white]statutory[/white]"
            )

            for line in statutory_lines[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")

        console.print()
