from pathlib import Path
from typing import Any

import orjson

PRONOM = Path(__file__).parent / "database"
CHANGES_URL = "https://www.nationalarchives.gov.uk/aboutapps/pronom/release-notes.xml"

REPO_FILE = Path(__file__).parent / "repo.json"
repository: dict[str, Any] = orjson.loads(REPO_FILE.read_bytes())

flags = {"all": False}
