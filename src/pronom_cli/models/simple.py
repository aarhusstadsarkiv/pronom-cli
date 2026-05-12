from dataclasses import dataclass

from pronom_cli.models.base import EntryABC
from pronom_cli.utils import LABEL_STYLE, PUID_STYLE, VALUE_STYLE, console, print_row


@dataclass
class SimpleEntry(EntryABC):
    def print(self, detailed: bool = False) -> None:
        console.print(
            f"[{PUID_STYLE}]{self.hexdigest()}[/{PUID_STYLE}]"
            + f"  [{VALUE_STYLE}]{self.name or '-'}[/{VALUE_STYLE}]"
            + (f"  [dim]({self.version})[/dim]" if self.version else "")
        )
        console.print()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
        else:
            console.print("[white]No description.[/white]")

        console.print()

        print_row("source", self.source)
        print_row("types", self.types or "-")
        print_row("created by", self.created_by or "-")
        print_row("extensions", "  ".join(self.extensions) if self.extensions else "-")

        seq_count = len(self.sequences)
        print_row(
            "sequences", f"{seq_count} byte sequence{'s' if seq_count != 1 else ''}"
        )

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

        console.print()
