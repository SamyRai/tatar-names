from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.abc import Traversable


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def rules_path(filename: str) -> Traversable:
    """Resolve a rule table bundled inside the package.

    Returns a Traversable so callers can read text directly whether the
    package is used from a checkout or an installed wheel. The anchor is
    passed positionally on purpose: ``files()`` took no keyword before
    Python 3.12, so a keyword call would break the supported range.
    """
    return files("tatar_names") / "rules" / filename


def default_release_dir() -> Path:
    return project_root() / "data" / "release"


def default_source_dir() -> Path:
    return project_root() / "data" / "source"


def release_path(filename: str, data_dir: str | Path | None = None) -> Path:
    base = Path(data_dir) if data_dir is not None else default_release_dir()
    return base / filename


def source_path(filename: str, data_dir: str | Path | None = None) -> Path:
    base = Path(data_dir) if data_dir is not None else default_source_dir()
    return base / filename
