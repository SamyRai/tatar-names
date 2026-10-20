"""Regression baseline measurements for the tatar-names toolkit.

Run from sdks/python:

    uv run python benchmarks/bench_baseline.py [--skip-scan]

Records row counts, SHA-256 hashes of every source and release table, and
timings for the known hot paths (cold resolve, the alias branch, and the
relation-coverage scan). Output is a single JSON object so runs stay
diffable across commits.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "sdks" / "python" / "src"))

from tatar_names import normalize, resolve  # noqa: E402
from tatar_names.data import default_release_dir, default_source_dir  # noqa: E402

TABLES = ("identities", "forms", "relations", "review_queue", "aliases")
SOURCE_TABLES = ("entities", "attestations", "excluded_entities")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def hash_tables(directory: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {f"{name}.csv": sha256(directory / f"{name}.csv") for name in names}


def first_alias_query() -> str:
    aliases = default_release_dir() / "aliases.csv"
    with aliases.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            return row["alias"]
    return "Гүзәл"


def timed_resolve(samples: int, alias_query: str) -> dict[str, float | int | str]:
    # Each resolve() call re-reads every release table today; sample exact and
    # alias-branch behaviour separately so the index work has an honest
    # before/after on the same query shapes.
    exact: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        result = resolve.resolve("Гүзәл")
        exact.append(time.perf_counter() - start)
    alias_branch: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        resolve.resolve(alias_query)
        alias_branch.append(time.perf_counter() - start)
    return {
        "samples": samples,
        "exact_query": "Гүзәл",
        "alias_query": alias_query,
        "exact_seconds_median": round(statistics.median(exact), 4),
        "exact_seconds_max": round(max(exact), 4),
        "alias_seconds_median": round(statistics.median(alias_branch), 4),
        "exact_candidate_rows": len(result["candidates"]),
    }


def timed_relation_coverage_scan() -> float:
    # Mirrors the audit names_without_relations computation (identity-count x
    # relation-count scan) so the measured path is the shipped one.
    from tatar_names import audit

    identities = audit.release_table(default_release_dir(), "identities")
    relations = audit.release_table(default_release_dir(), "relations")
    start = time.perf_counter()
    uncovered = sorted(
        row["name_id"]
        for row in identities
        if not any(
            relation["left_kind"] == "name" and relation["left_id"] == row["name_id"]
            or relation["right_kind"] == "name" and relation["right_id"] == row["name_id"]
            for relation in relations
        )
    )
    elapsed = time.perf_counter() - start
    print(f"relation-coverage scan: {elapsed:.2f}s, uncovered names: {len(uncovered)}", file=sys.stderr)
    return round(elapsed, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-scan", action="store_true", help="skip the multi-minute relation-coverage scan")
    parser.add_argument("--resolve-samples", type=int, default=3)
    args = parser.parse_args()

    release_dir = default_release_dir()
    source_dir = default_source_dir()

    report: dict[str, object] = {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
        "row_counts": {
            f"release/{name}.csv": table_row_count(release_dir / f"{name}.csv") for name in TABLES
        }
        | {f"source/{name}.csv": table_row_count(source_dir / f"{name}.csv") for name in SOURCE_TABLES},
        "release_sha256": hash_tables(release_dir, TABLES),
        "source_sha256": hash_tables(source_dir, SOURCE_TABLES),
        "resolve": timed_resolve(args.resolve_samples, first_alias_query()),
    }
    if not args.skip_scan:
        report["relation_coverage_scan_seconds"] = timed_relation_coverage_scan()

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
