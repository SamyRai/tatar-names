from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


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
