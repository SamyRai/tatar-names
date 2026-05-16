from __future__ import annotations

from pathlib import Path

from tatar_names.data import default_release_dir, default_source_dir
from tatar_names.pipeline import validate_release, validate_source


def validate_project(source_dir: str | Path | None = None, release_dir: str | Path | None = None) -> list[str]:
    source_base = Path(source_dir) if source_dir is not None else default_source_dir()
    release_base = Path(release_dir) if release_dir is not None else default_release_dir()
    errors = validate_source(source_base)
    errors.extend(validate_release(release_base))
    return errors


def main() -> None:
    errors = validate_project()
    if errors:
        raise SystemExit("Dataset validation failed:\n" + "\n".join(f"- {error}" for error in errors))


if __name__ == "__main__":
    main()
