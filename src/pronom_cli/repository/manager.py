import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import lru_cache
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fast_yaml import Loader, load
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pronom_cli import logger
from pronom_cli.models.action import parse_action
from pronom_cli.models.models import (
    Action,
    Extension,
    Format,
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
        """
        Fetches and parses PRONOM entry data for the supplied PUID, then inserts a
        new row or updates the existing one in the database.

        Parameters:
            puid: str
                The PRONOM unique identifier (PUID) for the file format.

        Returns:
            Format | None:
                The inserted or updated Format object, or None if the fetch or
                parse step fails.
        """
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
                fmt = Format(
                    source="Fileformats",
                    identifier=puid,
                    name=data["name"],
                    description=data.get("description", "No description provided"),
                    expires_at=int(time.time() + timedelta(days=1).total_seconds()),
                    extensions=extensions,
                    action=action,
                    sequences=signatures,
                )
                self.db_session.add(fmt)
                return fmt

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
        Fetches a Entry object corresponding to a specific identifier.

        This method retrieves a Entry object from a set of different repositories.
        Priority is given to ACA-specific PUIDs, which are exclusively fetched from file formats.
        For non-ACA PUIDs, the PRONOM repository gets searched through first. If an entry is found,
        additional actions are appended to it before returning the entry.

        Parameters:
            identifier: str
                The identifier used to fetch the corresponding Entry.

        Returns:
            Entry | None:
                A Entry object corresponding to the specified identifier if it
                exists, or None if no matching entry is found.
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

        return format

    def get_from_extension(self, ext: str, limit: int = 0) -> list[Format]:
        """
        Retrieves and merges repositories information for the given extension.

        This method combines the information given from the different repositories,
        for the provided file extension. The merging process ensures that entries
        from the `pronom` source take precedence over those from the `fileformats`
        source in cases of conflict, while also avoiding duplicate entries.

        Parameters:
            ext (str): The file extension for which format information is to
            be retrieved.

        Returns:
            list[Entry]: A list of `Entry` objects representing
            the merged information, or a list from a single source if the
            other source lacks data for the specified extension.
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
                selectinload(Format.master_action),
                selectinload(Format.extensions),
                selectinload(Format.sequences),
            )
        ).all()

        response = list(formats)
        for filter in filter_names:
            has_searched = self.db_session.scalar(
                select(RepositorySearches).filter(
                    RepositorySearches.query == ext,
                    RepositorySearches.repository == filter,
                )
            )

            if has_searched:
                continue

            repository = self.repositories.get(filter)

            if not repository:
                continue

            response.extend(repository.get(self.db_session, self.http_session, ext))

            self.db_session.add(RepositorySearches(repository=filter, query=ext))

        return response
