from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

from .data import default_release_dir

GITHUB_OWNER = "SamyRai"
GITHUB_REPO = "tatar-names"
DATASET_NAME = "tatar-names"
DATASET_TITLE = "Tatar Names"
DATASET_DESCRIPTION = "Tatar Names is a source-first dataset for auditable Tatar, Russian, and Latin name matching."
LICENSE_NAME = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CREATOR_NAME = "Damir Mukimov"
KEYWORDS = ("names", "tatar", "russian", "transliteration", "onomastics")
CROISSANT_CONFORMS_TO = "http://mlcommons.org/croissant/1.1"
# Croissant 1.1 files carry the expanded JSON-LD context (the 1.0 string form is
# rejected by the mlcroissant 1.1 reader); this is the spec's canonical mapping.
CROISSANT_CONTEXT: dict[str, object] = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "arrayShape": "cr:arrayShape",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "containedIn": "cr:containedIn",
    "cr": "http://mlcommons.org/croissant/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "description": {"@container": "@language"},
    "equivalentProperty": "cr:equivalentProperty",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "fileProperty": "cr:fileProperty",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isArray": "cr:isArray",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "name": {"@container": "@language"},
    "parentField": "cr:parentField",
    "path": "cr:path",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "samplingRate": "cr:samplingRate",
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}

# Release-time fallbacks keep builds byte-reproducible before a release is cut:
# the workflow sets SOURCE_DATE_EPOCH when the release tag is published, and the
# distribution version comes from installed package metadata (or this marker).
UNKNOWN_VERSION = "0.0.0+unknown"
EPOCH_FALLBACK_DATE = "1970-01-01T00:00:00Z"

# Column order mirrors cli.build.RELEASE_TABLES; test_metadata.py asserts the
# two stay in sync so the Croissant column bindings cannot drift from the build.
TABLES: dict[str, tuple[str, ...]] = {
    "identities": (
        "name_id",
        "entity_type",
        "gender",
        "origin_family",
        "usage_community",
        "canonical_tt_cyrl",
        "canonical_ru_cyrl",
        "canonical_tt_latn",
        "canonical_ru_latn",
        "primary_form_global",
        "primary_form_tt",
        "primary_form_ru",
        "source_id",
        "source_row",
        "status",
        "notes",
    ),
    "forms": (
        "form_id",
        "name_id",
        "form",
        "script",
        "language_tag",
        "form_role",
        "identity_status",
        "profile",
        "confidence",
        "source_id",
        "evidence_id",
        "merge_policy",
    ),
    "relations": (
        "relation_id",
        "left_kind",
        "left_id",
        "right_kind",
        "right_id",
        "relation",
        "merge_policy",
        "confidence",
        "evidence_type",
        "source_id",
        "evidence_id",
        "notes",
    ),
    "review_queue": (
        "review_id",
        "subject_kind",
        "subject_id",
        "queue_reason",
        "suggested_relation",
        "source_id",
        "evidence_id",
        "notes",
    ),
    "aliases": (
        "alias_id",
        "form_id",
        "name_id",
        "alias",
        "script",
        "language_tag",
        "alias_type",
        "method",
        "confidence",
        "merge_policy",
        "source_id",
        "rule_id",
    ),
}


def table_filename(table: str) -> str:
    return f"{table}.csv"


def table_schema_uri(version: str, table: str) -> str:
    # Raw GitHub URLs pinned to the release tag stay resolvable without auth and
    # inside source archives; release-asset URLs would need per-file attachments.
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/v{version}/schemas/tableschema/{table}.tableschema.json"


def dataset_release_url(version: str) -> str:
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/v{version}"


def installed_version() -> str:
    try:
        return importlib_metadata.version(DATASET_NAME)
    except importlib_metadata.PackageNotFoundError:
        return UNKNOWN_VERSION


def date_published_from_env() -> str:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if not raw:
        return EPOCH_FALLBACK_DATE
    try:
        epoch = int(raw)
    except ValueError:
        raise ValueError(f"SOURCE_DATE_EPOCH must be a non-negative integer, got {raw!r}") from None
    if epoch < 0:
        raise ValueError(f"SOURCE_DATE_EPOCH must be a non-negative integer, got {raw!r}")
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_object(release_dir: Path, table: str, dataset_url: str) -> dict[str, object]:
    data = (release_dir / table_filename(table)).read_bytes()
    return {
        "@type": "cr:FileObject",
        "@id": table_filename(table),
        "name": table_filename(table),
        "contentUrl": f"{dataset_url}/{table_filename(table)}",
        "encodingFormat": "text/csv",
        "sha256": hashlib.sha256(data).hexdigest(),
        "contentSize": f"{len(data)} B",
    }


def _record_set(table: str) -> dict[str, object]:
    fields = [
        {
            "@type": "cr:Field",
            "name": column,
            "dataType": "sc:Text",
            "source": {
                "fileObject": {"@id": table_filename(table)},
                "extract": {"column": column},
            },
        }
        for column in TABLES[table]
    ]
    return {"@type": "cr:RecordSet", "@id": table, "name": table, "field": fields}


def write_croissant(release_dir: Path, *, date_published: str, dataset_url: str) -> None:
    croissant = {
        "@context": CROISSANT_CONTEXT,
        "@type": "Dataset",
        "conformsTo": CROISSANT_CONFORMS_TO,
        "name": DATASET_TITLE,
        "description": DATASET_DESCRIPTION,
        "url": dataset_url,
        "license": LICENSE_URL,
        "creator": {"@type": "Person", "name": CREATOR_NAME},
        "keywords": list(KEYWORDS),
        "datePublished": date_published,
        "distribution": [_file_object(release_dir, table, dataset_url) for table in TABLES],
        "recordSet": [_record_set(table) for table in TABLES],
    }
    _write_json(release_dir / "croissant.json", croissant)


def write_datapackage(release_dir: Path, *, dataset_url: str, version: str) -> None:
    # Paths stay descriptor-relative per Data Package v2, so the release URL is
    # not emitted here; the parameter keeps release-time facts with one caller.
    del dataset_url
    datapackage = {
        # Canonical Data Package v2 profile URL: declares the descriptor
        # version without the v1-era "profile" key.
        "$schema": "https://datapackage.org/profiles/2.0/datapackage.json",
        "name": DATASET_NAME,
        "title": DATASET_TITLE,
        "description": DATASET_DESCRIPTION,
        "licenses": [{"name": LICENSE_NAME, "path": LICENSE_URL}],
        "resources": [
            {
                "name": table,
                "path": table_filename(table),
                "format": "csv",
                "mediatype": "text/csv",
                "encoding": "utf-8",
                "schema": table_schema_uri(version, table),
            }
            for table in TABLES
        ],
    }
    _write_json(release_dir / "datapackage.json", datapackage)


def _frictionless_error_note(error: object) -> str:
    if isinstance(error, dict):
        return str(error.get("note") or error.get("message") or error)
    return str(error)


def _frictionless_errors(datapackage_path: Path) -> tuple[list[str], str | None]:
    try:
        from frictionless import Package
    except ImportError:
        return [], (
            "frictionless is not installed; install the metadata dependency group to validate the Data Package descriptor"
        )
    try:
        descriptor = json.loads(datapackage_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"datapackage.json failed frictionless validation: {error}"], None
    # Descriptor-level validation: resource schemas are tag-pinned URIs that
    # 404 until the release tag exists, so CSV rows are not re-read here.
    try:
        metadata_errors = list(Package.metadata_validate(descriptor))
    except Exception as error:
        return [f"datapackage.json failed frictionless validation: {error}"], None
    return [
        f"datapackage.json failed frictionless validation: {_frictionless_error_note(error)}"
        for error in metadata_errors
    ], None


def _mlcroissant_errors(croissant_path: Path) -> tuple[list[str], str | None]:
    try:
        import mlcroissant
    except ImportError:
        return [], (
            "mlcroissant is not installed; install the metadata dependency group to validate the Croissant metadata"
        )
    # The 1.1 reader validates while parsing and raises on structural errors;
    # recommended-property findings are warnings and keep construction alive.
    try:
        mlcroissant.Dataset(jsonld=str(croissant_path))
    except Exception as error:
        return [f"croissant.json failed Croissant validation: {error}"], None
    return [], None


def validate_metadata(release_dir: Path) -> tuple[list[str], list[str]]:
    """Validate generated metadata with the optional validators.

    Returns (errors, skipped): errors fail the run, skipped holds one notice per
    validator that is not importable so callers can surface a clear reason.
    """
    errors: list[str] = []
    skipped: list[str] = []
    datapackage_errors, datapackage_skipped = _frictionless_errors(release_dir / "datapackage.json")
    errors.extend(datapackage_errors)
    if datapackage_skipped:
        skipped.append(datapackage_skipped)
    croissant_errors, croissant_skipped = _mlcroissant_errors(release_dir / "croissant.json")
    errors.extend(croissant_errors)
    if croissant_skipped:
        skipped.append(croissant_skipped)
    return errors, skipped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate the generated dataset metadata files.")
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=None,
        help="directory holding datapackage.json and croissant.json (default: data/release)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="run frictionless and mlcroissant validation when the metadata dependency group is installed",
    )
    args = parser.parse_args(argv)
    if not args.validate:
        parser.error("nothing to do: pass --validate")

    release_dir = args.release_dir if args.release_dir is not None else default_release_dir()
    if not release_dir.is_dir():
        print(f"error: release directory not found: {release_dir}", file=sys.stderr)
        raise SystemExit(2)
    for filename in ("datapackage.json", "croissant.json"):
        if not (release_dir / filename).is_file():
            print(f"error: {filename} not found in {release_dir}", file=sys.stderr)
            raise SystemExit(2)

    errors, skipped = validate_metadata(release_dir)
    for notice in skipped:
        print(f"skipped: {notice}")
    if errors:
        raise SystemExit("Metadata validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    if len(skipped) == 2:
        print(f"OK: metadata files present, but no validator was installed ({release_dir})")
    else:
        print(f"OK: dataset metadata valid ({release_dir})")


if __name__ == "__main__":
    main()
