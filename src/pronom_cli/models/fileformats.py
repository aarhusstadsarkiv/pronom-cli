from dataclasses import dataclass
from typing import Any

from pronom_cli.models.action import ActionABC, parse_action
from pronom_cli.models.base import EntryABC
from pronom_cli.utils import (
    LABEL_STYLE,
    PUID_STYLE,
    VALUE_STYLE,
    action_style,
    console,
    print_row,
)


@dataclass
class FileFormatsEntry(EntryABC):
    puid: str = ""
    action: ActionABC | None = None

    source: str = "Fileformats"

    @property
    def is_aca(self) -> bool:
        return self.puid.startswith("aca-")

    @classmethod
    def from_yaml(cls, puid: str, data: dict[str, Any]) -> "FileFormatsEntry":
        return cls(
            puid=puid,
            name=data["name"],
            description=data.get("description", ""),
            extensions=data.get("extensions", []),
            action=parse_action(data),
        )

    def print(self, detailed: bool = False):
        console.print(
            f"[{PUID_STYLE}]{self.puid or '-'}[/{PUID_STYLE}]"
            f"  [{VALUE_STYLE}]{self.name or '-'}[/{VALUE_STYLE}]"
            + (f"  [dim]({self.version})[/dim]" if self.version else "")
        )
        console.print()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
        else:
            console.print("[white]No description was given in fileformats.[/white]")

        console.print()

        print_row("extensions", "  ".join(self.extensions) if self.extensions else "-")

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

        if self.action:
            action_lines = self.action.print().splitlines()
            action_name = action_lines[0]
            style = action_style(action_name)

            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [{style}]{action_name}[/{style}]"
            )
            for line in action_lines[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")
        else:
            print_row("action", "-")

        console.print()
