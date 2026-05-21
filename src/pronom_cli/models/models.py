from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pronom_cli.models.base import Base
from pronom_cli.utils import (
    LABEL_STYLE,
    PUID_STYLE,
    VALUE_STYLE,
    action_style,
    console,
    print_row,
)


class Format(Base):
    __tablename__ = "formats"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)

    source: Mapped[str]
    name: Mapped[str]
    identifier: Mapped[str] = mapped_column(nullable=False, unique=True)
    version: Mapped[str | None]
    description: Mapped[str]
    classification: Mapped[str | None]
    created_by: Mapped[str | None]
    creation_date: Mapped[str | None]
    family: Mapped[str | None]
    expires_at: Mapped[int | None]

    extensions: Mapped[list["Extension"]] = relationship(
        back_populates="format", cascade="all, delete-orphan"
    )

    sequences: Mapped[list["Sequence"]] = relationship(
        back_populates="format", cascade="all, delete-orphan"
    )

    action: Mapped["Action | None"] = relationship(
        "Action", back_populates="format", uselist=False, cascade="all, delete-orphan"
    )

    master_action: Mapped["MasterAction | None"] = relationship(
        "MasterAction",
        back_populates="format",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def is_aca(self) -> bool:
        return self.identifier.startswith("aca-")

    def print(self, detailed: bool = False) -> None:
        if self.source == "PRONOM":
            self._print_pronom(detailed)
        elif self.source == "Fileformats":
            self._print_fileformats(detailed)
        else:
            self._print_simple(detailed)

    def _print_header(self) -> None:
        console.print(
            f"[{PUID_STYLE}]{self.identifier}[/{PUID_STYLE}]"
            f"  [{VALUE_STYLE}]{self.name or '-'}[/{VALUE_STYLE}]"
            + (f"  [dim]({self.version})[/dim]" if self.version else "")
        )
        console.print()

    def _print_sequences(self) -> None:
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

    def _print_action(self, action_str: str) -> None:
        lines = action_str.splitlines()
        name = lines[0]
        console.print(
            f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}]"
            f" [{action_style(name)}]{name}[/{action_style(name)}]"
        )
        for line in lines[1:]:
            console.print(f"[dim]{'':13}{line}[/dim]")

    def _print_pronom(self, detailed: bool) -> None:
        exts = [e.extension for e in self.extensions]
        self._print_header()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
            console.print()

        print_row("family", self.family or "-")
        print_row("created by", self.created_by or "-")
        print_row("types", self.classification or "-")
        print_row("extensions", "  ".join(exts) if exts else "-")

        seq_count = len(self.sequences)
        print_row(
            "sequences", f"{seq_count} byte sequence{'s' if seq_count != 1 else ''}"
        )

        if detailed:
            console.print()
            print_row("created", self.creation_date or "-")
            if self.sequences:
                console.print()
                self._print_sequences()

        if self.action:
            console.print()
            console.print(
                "[white][bold]record was also found in fileformats[/bold][/white]"
            )
            print_row("description", self.action.description or "-")
            self._print_action(self.action.action)

        if self.master_action:
            console.print()
            console.print(
                "[white][bold]record was also found in fileformats-master[/bold][/white]"
            )
            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [white]access[/white]"
            )
            for line in self.master_action.access.splitlines()[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")
            console.print()
            console.print(
                f"[{LABEL_STYLE}]{'action':<12}[/{LABEL_STYLE}] [white]statutory[/white]"
            )
            for line in self.master_action.statutory.splitlines()[1:]:
                console.print(f"[dim]{'':13}{line}[/dim]")

        console.print()

    def _print_fileformats(self, detailed: bool) -> None:
        exts = [e.extension for e in self.extensions]
        self._print_header()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
        else:
            console.print("[white]No description was given in fileformats.[/white]")

        console.print()
        print_row("extensions", "  ".join(exts) if exts else "-")

        if self.sequences:
            console.print()
            self._print_sequences()

        console.print()

        if self.action:
            self._print_action(self.action.action)
        else:
            print_row("action", "-")

        console.print()

    def _print_simple(self, detailed: bool) -> None:
        exts = [e.extension for e in self.extensions]
        self._print_header()

        if self.description:
            console.print(f"[white]{self.description.strip()}[/white]")
        else:
            console.print("[white]No description.[/white]")

        console.print()
        print_row("source", self.source)
        print_row("types", self.classification or "-")
        print_row("created by", self.created_by or "-")
        print_row("extensions", "  ".join(exts) if exts else "-")

        seq_count = len(self.sequences)
        print_row(
            "sequences", f"{seq_count} byte sequence{'s' if seq_count != 1 else ''}"
        )

        if self.sequences:
            console.print()
            self._print_sequences()

        console.print()


class Extension(Base):
    __tablename__ = "extensions"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)

    extension: Mapped[str]
    entry_id: Mapped[int] = mapped_column(ForeignKey("formats.id", ondelete="CASCADE"))

    format: Mapped["Format"] = relationship("Format", back_populates="extensions")


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entry_id: Mapped[int] = mapped_column(ForeignKey("formats.id", ondelete="CASCADE"))
    name: Mapped[str]
    note: Mapped[str | None]
    offset: Mapped[int] = mapped_column(default=0)
    max_offset: Mapped[int] = mapped_column(default=0)
    position: Mapped[str | None]
    sequence: Mapped[str | None]

    format: Mapped["Format"] = relationship(back_populates="sequences")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("formats.id", ondelete="CASCADE"), unique=True
    )
    description: Mapped[str | None]
    action: Mapped[str]

    format: Mapped["Format"] = relationship("Format", back_populates="action")


class MasterAction(Base):
    __tablename__ = "master_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("formats.id", ondelete="CASCADE"), unique=True
    )
    access: Mapped[str]
    statutory: Mapped[str]

    format: Mapped["Format"] = relationship("Format", back_populates="master_action")


class RepositorySearches(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    repository: Mapped[str]
    query: Mapped[str]
