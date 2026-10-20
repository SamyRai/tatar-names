from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tatar_names.audit import analyze_patterns
from tatar_names.data import default_release_dir, default_source_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarize dataset coverage and pattern signals.")
    parser.add_argument("--source-dir", type=Path, default=None, help="source data directory (default: data/source)")
    parser.add_argument("--release-dir", type=Path, default=None, help="release data directory (default: data/release)")
    parser.add_argument("--sample-limit", type=int, default=10, help="maximum number of examples per signal (default: 10)")
    args = parser.parse_args(argv)
    if args.sample_limit < 1:
        parser.error("--sample-limit must be a positive integer")

    source_dir = args.source_dir if args.source_dir is not None else default_source_dir()
    release_dir = args.release_dir if args.release_dir is not None else default_release_dir()
    for label, path in (("source", source_dir), ("release", release_dir)):
        if not path.is_dir():
            print(f"error: {label} directory not found: {path}", file=sys.stderr)
            raise SystemExit(2)
    try:
        report = analyze_patterns(source_dir, release_dir, args.sample_limit)
    except OSError as error:
        print(f"error: cannot read dataset: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
