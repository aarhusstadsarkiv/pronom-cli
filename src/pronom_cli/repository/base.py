from abc import ABC, abstractmethod

import httpx
from sqlalchemy.orm import Session

from pronom_cli.models.models import Format


class Repository(ABC):
    @abstractmethod
    def get(
        self, db_session: Session, http_session: httpx.Client, key: str
    ) -> list[Format]:
        pass
