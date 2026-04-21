from __future__ import annotations

import abc
from pathlib import Path

from dep_age.models import Dependency, Ecosystem


class BaseParser(abc.ABC):
    ecosystem: Ecosystem
    lock_filenames: list[str]

    @abc.abstractmethod
    def parse(self, path: Path) -> list[Dependency]: ...

    def can_handle(self, path: Path) -> bool:
        return path.name in self.lock_filenames
