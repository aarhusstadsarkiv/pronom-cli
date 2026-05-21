from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pronom_cli.models.base import Base


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
        return self.name.startswith("aca-")


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
