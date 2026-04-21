from dep_age.parsers.base import BaseParser
from dep_age.parsers.cargo_parser import CargoParser
from dep_age.parsers.composer_parser import ComposerParser
from dep_age.parsers.gem_parser import GemParser
from dep_age.parsers.go_parser import GoParser
from dep_age.parsers.npm_parser import NpmParser
from dep_age.parsers.pip_parser import PipParser

ALL_PARSERS: list[type[BaseParser]] = [
    NpmParser,
    PipParser,
    GemParser,
    GoParser,
    CargoParser,
    ComposerParser,
]

__all__ = [
    "BaseParser",
    "NpmParser",
    "PipParser",
    "GemParser",
    "GoParser",
    "CargoParser",
    "ComposerParser",
    "ALL_PARSERS",
]
