from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tatar_names.data import default_release_dir, default_source_dir
from tatar_names.pipeline import validate_release, validate_source


def validate_project(source_dir: str | Path | None = None, release_dir: str | Path | None = None) -> list[str]:
    source_base = Path(source_dir) if source_dir is not None else default_source_dir()
    release_base = Path(release_dir) if release_dir is not None else default_release_dir()
    errors = validate_source(source_base)
    errors.extend(validate_release(release_base))
    return errors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate the source dataset and the built release tables.")
    parser.add_argument("--source-dir", type=Path, default=None, help="source data directory (default: data/source)")
    parser.add_argument("--release-dir", type=Path, default=None, help="release data directory (default: data/release)")
    parser.add_argument("--quiet", action="store_true", help="suppress the success message")
    args = parser.parse_args(argv)

    source_dir = args.source_dir if args.source_dir is not None else default_source_dir()
    release_dir = args.release_dir if args.release_dir is not None else default_release_dir()
    for label, path in (("source", source_dir), ("release", release_dir)):
        if not path.is_dir():
            print(f"error: {label} directory not found: {path}", file=sys.stderr)
            raise SystemExit(2)
    try:
        errors = validate_project(source_dir, release_dir)
    except OSError as error:
        print(f"error: cannot read dataset: {error}", file=sys.stderr)
        raise SystemExit(2)
    if errors:
        raise SystemExit("Dataset validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    if not args.quiet:
        print(f"OK: source and release tables valid ({source_dir}, {release_dir})")


if __name__ == "__main__":
    main()
