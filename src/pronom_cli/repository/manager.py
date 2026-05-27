import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import lru_cache
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fast_yaml import Loader, load
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from pronom_cli import logger
from pronom_cli.models.action import parse_action
from pronom_cli.models.models import (
    Action,
    Extension,
    Format,
    MasterAction,
    RepositorySearches,
    Sequence,
)
from pronom_cli.repository.base import Repository
from pronom_cli.repository.fileinfo import FileInfoRepository
from pronom_cli.repository.fileproinfo import FileProInfoRepository
from pronom_cli.repository.filext import FilextRepository
from pronom_cli.utils import (
    Filter,
    filters_to_names,
    find_xml,
    search_custom_signatures,
)

FILEFORMATS_FILE = "fileformats.yml"
CUSTOM_SIGNATURES_FILE = "custom_signatures.yml"


@lru_cache
def _load_from_github(session: httpx.Client, filename: str) -> Any:
    """Fetches and parses a YAML file from aarhusstadsarkiv/reference-files; result is cached."""
    response = session.get(
        f"https://raw.githubusercontent.com/aarhusstadsarkiv/reference-files/refs/heads/main/{filename}"
    )
    if response.status_code != 200:
        logger.error(f"failed to fetch {filename} from github")
        return
    return load(response.text, Loader=Loader)


def _add_custom_sequences(
    custom_signatures: list[dict[str, Any]], puid: str
) -> list[Sequence]:
    """Search for and add custom BOF/EOF sequences to an ACA format."""
    seq_from_yml = search_custom_signatures(custom_signatures, puid)
    if not seq_from_yml:
        return []

    name = seq_from_yml["signature"]
    note = seq_from_yml.get("description", "")

    sequences = []

    for key, label in (("bof", "BOF"), ("eof", "EOF")):
        sequence = seq_from_yml.get(key)
        if not sequence:
            continue

        sequences.append(
            Sequence(
                name=name,
                note=note,
                offset=0,
                max_offset=0,
                position=label,
                sequence=sequence,
            )
        )

    return sequences


class RepositoryManager:
    repositories: dict[str, Repository] = {
        "filext": FilextRepository(),
        "fileproinfo": FileProInfoRepository(),
        "fileinfo": FileInfoRepository(),
    }

    def __init__(
        self,
        db_session: Session,
        http_session: httpx.Client,
        filters: list[Filter],
    ):
        self.db_session = db_session
        self.http_session = http_session
        self.filters = filters

    def _get_from_pronom(self, puid: str) -> Format | None:
        """Fetches PRONOM XML for the given PUID and inserts or updates the Format row."""
        pronom_response = self.http_session.get(
            "http://www.nationalarchives.gov.uk/PRONOM/" + puid
        )

        soup = BeautifulSoup(pronom_response.text, "html.parser")

        form = soup.find(id="frmSaveAs")

        if not form:
            return

        format_id_input = form.find("input", attrs={"name": "strFileFormatID"})
        format_id = format_id_input.get("value") if format_id_input else None

        response = self.http_session.get(
            "https://www.nationalarchives.gov.uk/PRONOM/Format/proFormatDetailListAction.aspx",
            params={"strAction": "Save As XML", "strFileFormatID": format_id},
        )

        if response.status_code != 200:
            return

        content = response.text

        if "The following errors were reported:" in content:
            return

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.error("failed to parse response from pronom. maybe ratelimiting?")
            return

        new_extensions = []
        if signs := root.findall(".//{*}ExternalSignature"):
            for sign in signs:
                if (signature := sign.find("{*}Signature")) is None:
                    logger.warn("Signature not found")
                    continue
                new_extensions.append(Extension(extension=signature.text))  # type: ignore

        new_sequences = []
        if signs := root.findall(".//{*}ByteSequence"):
            for sign in signs:
                new_sequences.append(
                    Sequence(
                        name=find_xml(root, ".//{*}SignatureName"),
                        note=find_xml(root, ".//{*}SignatureNote"),
                        offset=int(find_xml(sign, ".//{*}Offset", "0")),
                        max_offset=int(find_xml(sign, ".//{*}MaxOffset", "0")),
                        position=find_xml(sign, ".//{*}PositionType"),
                        sequence=find_xml(sign, ".//{*}ByteSequenceValue"),
                    )
                )

        existing = self.db_session.scalars(
            select(Format).where(Format.identifier == puid)
        ).one_or_none()

        if existing:
            existing.name = find_xml(root, ".//{*}FormatName")
            existing.version = find_xml(root, ".//{*}FormatVersion")
            existing.description = find_xml(root, ".//{*}FormatDescription")
            existing.created_by = find_xml(root, ".//{*}ProvenanceName")
            existing.creation_date = find_xml(root, ".//{*}ProvenanceSourceDate")
            existing.classification = find_xml(root, ".//{*}FormatTypes")
            existing.family = find_xml(root, ".//{*}FormatFamilies")
            existing.extensions = new_extensions
            existing.sequences = new_sequences
            return existing

        entry = Format(
            source="PRONOM",
            identifier=puid,
            name=find_xml(root, ".//{*}FormatName"),
            version=find_xml(root, ".//{*}FormatVersion"),
            description=find_xml(root, ".//{*}FormatDescription"),
            created_by=find_xml(root, ".//{*}ProvenanceName"),
            creation_date=find_xml(root, ".//{*}ProvenanceSourceDate"),
            classification=find_xml(root, ".//{*}FormatTypes"),
            family=find_xml(root, ".//{*}FormatFamilies"),
            extensions=new_extensions,
            sequences=new_sequences,
        )
        self.db_session.add(entry)

        return entry

    def _get_from_fileformats(self, identifier: str) -> Format | None:
        """Fetches fileformats.yml and custom_signatures.yml and inserts or updates the ACA Format row."""
        with ThreadPoolExecutor(max_workers=2) as executor:
            fileformats_thread = executor.submit(
                _load_from_github, self.http_session, FILEFORMATS_FILE
            )
            signatures_thread = executor.submit(
                _load_from_github, self.http_session, CUSTOM_SIGNATURES_FILE
            )
            fileformats_yaml = fileformats_thread.result()
            signatures_yaml = signatures_thread.result()

        if not fileformats_yaml:
            return

        for puid, data in fileformats_yaml.items():
            if puid != identifier or not puid.startswith("aca-fmt"):
                continue

            action = Action(
                description=data.get("description"),
                action=str(parse_action(data)),
            )
            extensions = [
                Extension(extension=ext) for ext in data.get("extensions", [])
            ]
            signatures = _add_custom_sequences(signatures_yaml, identifier)

            existing = self.db_session.scalars(
                select(Format).where(Format.identifier == identifier)
            ).one_or_none()

            if not existing:
                entry = Format(
                    source="Fileformats",
                    identifier=puid,
                    name=data["name"],
                    description=data.get("description", "No description provided"),
                    expires_at=int(time.time() + timedelta(days=1).total_seconds()),
                    extensions=extensions,
                    action=action,
                    sequences=signatures,
                )
                self.db_session.add(entry)
                return entry

            existing.name = data["name"]
            existing.description = data.get("description", "No description provided")
            existing.expires_at = int(time.time() + timedelta(days=1).total_seconds())
            existing.extensions = extensions
            existing.sequences = signatures
            if existing.action:
                existing.action.description = action.description
                existing.action.action = action.action
            else:
                existing.action = action
            return existing

    def get_from_identifier(self, identifier: str) -> Format | None:
        """
        Returns the Format for the given identifier, fetching from source if absent or expired.

        ACA identifiers are resolved against fileformats.yml; all others go to PRONOM.
        Master action is attached before returning.
        """
        stmt = (
            select(Format)
            .where(Format.identifier == identifier)
            .options(
                selectinload(Format.action),
                selectinload(Format.master_action),
                selectinload(Format.extensions),
                selectinload(Format.sequences),
            )
        )
        format = self.db_session.scalars(stmt).one_or_none()

        if not format:
            # We only account for fileformats and pronom
            # since the other repositories only have
            # identifiers upon discovery in extensions
            if identifier.startswith("aca-"):
                format = self._get_from_fileformats(identifier)
            else:
                format = self._get_from_pronom(identifier)

            if not format:
                return None

        if format.expires_at and format.expires_at < time.time():
            logger.warn("format has expired, updating from source.")
            if identifier.startswith("aca-"):
                format = self._get_from_fileformats(identifier)
            else:
                format = self._get_from_pronom(identifier)

            if not format:
                return None

        master = self.db_session.scalar(
            select(MasterAction)
            .where(
                or_(
                    MasterAction.entry_identifier == format.identifier,
                    MasterAction.classification == func.lower(format.classification),
                )
            )
            .limit(1)
        )
        format.master_action = master

        return format

    def get_from_extension(self, ext: str, limit: int = 0) -> list[Format]:
        """
        Returns all Format records matching the extension across active repositories.

        Database results are returned first; each repository that hasn't been queried
        for this extension yet is scraped and its results appended. Master actions are
        attached inline. Pass limit > 0 to cap the result count.
        """
        filter_names = filters_to_names(self.filters)

        formats = self.db_session.scalars(
            select(Format)
            .join(Extension.format)
            .filter(
                Extension.extension == ext, func.lower(Format.source).in_(filter_names)
            )
            .options(
                selectinload(Format.action),
                selectinload(Format.extensions),
                selectinload(Format.sequences),
            )
        ).all()

        identifiers = [format.identifier for format in formats]
        classifications = [format.classification for format in formats]

        master_actions = self.db_session.scalars(
            select(MasterAction).where(
                or_(
                    MasterAction.entry_identifier.in_(identifiers),
                    func.lower(MasterAction.classification).in_(
                        [c.lower() for c in classifications if c]
                    ),
                )
            )
        ).all()

        by_identifier = {ma.entry_identifier: ma for ma in master_actions}
        by_classification = {
            (ma.classification.lower() if ma.classification else None): ma
            for ma in master_actions
        }

        for format in formats:
            format.master_action = by_identifier.get(format.identifier) or (
                by_classification.get(format.classification.lower())
                if format.classification
                else None
            )

        response = list(formats)

        for filter in filter_names:
            has_searched = self.db_session.scalar(
                select(RepositorySearches).filter(
                    RepositorySearches.query == ext,
                    RepositorySearches.repository == filter,
                )
            )

            if has_searched:
                expiration = has_searched.expires_at

                if expiration < int(time.time()):
                    self.db_session.delete(has_searched)
                else:
                    continue

            repository = self.repositories.get(filter)

            if not repository:
                continue

            response.extend(repository.get(self.db_session, self.http_session, ext))

            self.db_session.add(
                RepositorySearches(
                    repository=filter,
                    query=ext,
                    expires_at=int(time.time() + timedelta(weeks=8).total_seconds()),
                )
            )

        return response[:limit] if limit > 0 else response
