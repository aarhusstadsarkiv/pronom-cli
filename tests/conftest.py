import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pronom_cli.models.base import Base
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.utils import Filter

GITHUB_BASE = "https://raw.githubusercontent.com/aarhusstadsarkiv/reference-files/refs/heads/main/"

PRONOM_HTML = """
<html><body>
<form id="frmSaveAs">
  <input name="strFileFormatID" value="42" />
</form>
</body></html>
"""

PRONOM_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<PRONOM-Report>
  <report_format_detail>
    <FormatName>Test Format</FormatName>
    <FormatVersion>1.0</FormatVersion>
    <FormatDescription>A test format description</FormatDescription>
    <ProvenanceName>Test Corp</ProvenanceName>
    <ProvenanceSourceDate>2020-01-01</ProvenanceSourceDate>
    <FormatTypes>Text</FormatTypes>
    <FormatFamilies>Office</FormatFamilies>
    <SignatureName>Test Signature</SignatureName>
    <SignatureNote>test note</SignatureNote>
    <ExternalSignature>
      <Signature>txt</Signature>
    </ExternalSignature>
    <ByteSequence>
      <Offset>0</Offset>
      <MaxOffset>0</MaxOffset>
      <PositionType>BOF</PositionType>
      <ByteSequenceValue>AABBCC</ByteSequenceValue>
    </ByteSequence>
  </report_format_detail>
</PRONOM-Report>
"""

PRONOM_XML_NO_SIGS = """\
<?xml version="1.0" encoding="utf-8"?>
<PRONOM-Report>
  <report_format_detail>
    <FormatName>Test Format</FormatName>
    <FormatVersion>1.0</FormatVersion>
    <FormatDescription>A test format description</FormatDescription>
    <ProvenanceName>Test Corp</ProvenanceName>
    <ProvenanceSourceDate>2020-01-01</ProvenanceSourceDate>
    <FormatTypes>Text</FormatTypes>
    <FormatFamilies>Office</FormatFamilies>
  </report_format_detail>
</PRONOM-Report>
"""

FILEFORMATS_YAML = """\
aca-fmt/1:
  name: ACA Test Format
  description: A test ACA format
  extensions:
    - .tst
  action: convert
  convert:
    tool: someconverter
    output: .pdf
"""

FILEFORMATS_YAML_NO_EXTS = """\
aca-fmt/1:
  name: ACA Test Format
  description: A test ACA format
  action: convert
  convert:
    tool: someconverter
    output: .pdf
"""

FILEFORMATS_YAML_EMPTY = "{}\n"

CUSTOM_SIGNATURES_YAML = """\
- puid: aca-fmt/1
  signature: Test Signature
  description: test note
  bof: "AABBCC"
"""

# No custom signatures.
CUSTOM_SIGNATURES_YAML_EMPTY = "[]\n"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def manager(db_session: Session):
    return RepositoryManager(db_session, httpx.Client(), list(Filter))
