"""Semantic goldens for the Croissant and Data Package metadata generators."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tatar_names import metadata
from tatar_names.cli import build as build_cli

RELEASE_TABLES = {
    table: (filename, tuple(columns)) for table, (filename, columns) in build_cli.RELEASE_TABLES.items()
}


def write_release_fixture(release_dir: Path) -> dict[str, bytes]:
    release_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {}
    for filename, columns in RELEASE_TABLES.values():
        payload = (",".join(columns) + "\n" + ",".join(f"value_{column}" for column in columns) + "\n").encode("utf-8")
        (release_dir / filename).write_bytes(payload)
        payloads[filename] = payload
    return payloads


@pytest.fixture()
def release_dir(tmp_path: Path) -> dict[str, object]:
    payloads = write_release_fixture(tmp_path / "release")
    metadata.write_croissant(
        tmp_path / "release",
        date_published="2026-10-20T00:00:00Z",
        dataset_url="https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0",
    )
    metadata.write_datapackage(
        tmp_path / "release",
        dataset_url="https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0",
        version="0.1.0",
    )
    return {
        "payloads": payloads,
        "croissant": json.loads((tmp_path / "release" / "croissant.json").read_text(encoding="utf-8")),
        "datapackage": json.loads((tmp_path / "release" / "datapackage.json").read_text(encoding="utf-8")),
    }


def test_tables_stay_in_sync_with_build_columns() -> None:
    assert metadata.TABLES == {table: columns for table, (_, columns) in RELEASE_TABLES.items()}


def test_croissant_carries_required_1_1_properties(release_dir: dict[str, object]) -> None:
    croissant = release_dir["croissant"]
    assert croissant["@context"] == metadata.CROISSANT_CONTEXT
    assert croissant["@type"] == "Dataset"
    assert croissant["conformsTo"] == "http://mlcommons.org/croissant/1.1"
    assert croissant["name"] == "Tatar Names"
    assert croissant["description"]
    assert croissant["url"] == "https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0"
    assert croissant["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert croissant["creator"] == {"@type": "Person", "name": "Damir Mukimov"}
    assert croissant["keywords"] == ["names", "tatar", "russian", "transliteration", "onomastics"]
    assert croissant["datePublished"] == "2026-10-20T00:00:00Z"


def test_croissant_uses_file_objects_with_real_digests(release_dir: dict[str, object]) -> None:
    croissant = release_dir["croissant"]
    payloads: dict[str, bytes] = release_dir["payloads"]
    distribution = croissant["distribution"]
    assert len(distribution) == len(RELEASE_TABLES)
    assert "DataDownload" not in json.dumps(croissant)
    for file_object in distribution:
        assert file_object["@type"] == "cr:FileObject"
        assert file_object["encodingFormat"] == "text/csv"
        payload = payloads[file_object["name"]]
        assert file_object["sha256"] == hashlib.sha256(payload).hexdigest()
        assert file_object["contentSize"] == f"{len(payload)} B"
        assert file_object["contentUrl"] == (
            "https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0/" + file_object["name"]
        )
    assert {file_object["name"] for file_object in distribution} == {name for name, _ in RELEASE_TABLES.values()}


def test_croissant_record_sets_bind_every_column_to_its_file(release_dir: dict[str, object]) -> None:
    croissant = release_dir["croissant"]
    record_sets = {record_set["name"]: record_set for record_set in croissant["recordSet"]}
    assert set(record_sets) == set(RELEASE_TABLES)
    for table, (filename, columns) in RELEASE_TABLES.items():
        record_set = record_sets[table]
        assert record_set["@type"] == "cr:RecordSet"
        assert [field["name"] for field in record_set["field"]] == list(columns)
        for field in record_set["field"]:
            assert field["source"]["fileObject"] == {"@id": filename}
            assert field["source"]["extract"] == {"column": field["name"]}


def test_datapackage_is_v2_with_tag_pinned_schema_uris(release_dir: dict[str, object]) -> None:
    datapackage = release_dir["datapackage"]
    assert "profile" not in datapackage
    assert datapackage["$schema"] == "https://datapackage.org/profiles/2.0/datapackage.json"
    assert datapackage["name"] == "tatar-names"
    assert datapackage["title"] == "Tatar Names"
    assert datapackage["description"]
    assert datapackage["licenses"] == [
        {"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}
    ]
    resources = {resource["name"]: resource for resource in datapackage["resources"]}
    assert set(resources) == set(RELEASE_TABLES)
    for table, (filename, _) in RELEASE_TABLES.items():
        resource = resources[table]
        assert resource["path"] == filename
        assert resource["format"] == "csv"
        assert resource["mediatype"] == "text/csv"
        assert resource["encoding"] == "utf-8"
        assert resource["schema"] == (
            f"https://raw.githubusercontent.com/SamyRai/tatar-names/v0.1.0/schemas/tableschema/{table}.tableschema.json"
        )
    # The release URL belongs to the Croissant contentUrls; the Data Package
    # keeps descriptor-relative paths, so dataset_url is never emitted here.
    assert "github.com" not in json.dumps(datapackage)


def test_generation_is_byte_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for release_dir in (first, second):
        write_release_fixture(release_dir)
        metadata.write_croissant(
            release_dir,
            date_published="2026-10-20T00:00:00Z",
            dataset_url="https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0",
        )
        metadata.write_datapackage(
            release_dir,
            dataset_url="https://github.com/SamyRai/tatar-names/releases/tag/v0.1.0",
            version="0.1.0",
        )
    for filename in ("croissant.json", "datapackage.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_source_date_epoch_drives_date_published(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1792454400")
    expected = datetime.fromtimestamp(1792454400, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert metadata.date_published_from_env() == expected

    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert metadata.date_published_from_env() == "1970-01-01T00:00:00Z"

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
    with pytest.raises(ValueError, match="SOURCE_DATE_EPOCH"):
        metadata.date_published_from_env()


def test_version_falls_back_when_distribution_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing(name: str) -> str:
        raise metadata.importlib_metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata.importlib_metadata, "version", raise_missing)
    assert metadata.installed_version() == "0.0.0+unknown"
    assert metadata.table_schema_uri("0.0.0+unknown", "identities") == (
        "https://raw.githubusercontent.com/SamyRai/tatar-names/v0.0.0+unknown/schemas/tableschema/identities.tableschema.json"
    )


def test_validate_metadata_skips_absent_validators_with_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_release_fixture(tmp_path)
    metadata.write_croissant(tmp_path, date_published="2026-10-20T00:00:00Z", dataset_url="https://example.test/v0.1.0")
    metadata.write_datapackage(tmp_path, dataset_url="https://example.test/v0.1.0", version="0.1.0")

    monkeypatch.setitem(sys.modules, "frictionless", None)
    monkeypatch.setitem(sys.modules, "mlcroissant", None)
    errors, skipped = metadata.validate_metadata(tmp_path)

    assert errors == []
    assert len(skipped) == 2
    assert any("frictionless" in notice for notice in skipped)
    assert any("mlcroissant" in notice for notice in skipped)


def test_validate_metadata_flags_legacy_v1_descriptor(tmp_path: Path) -> None:
    pytest.importorskip("frictionless")
    write_release_fixture(tmp_path)
    metadata.write_croissant(tmp_path, date_published="2026-10-20T00:00:00Z", dataset_url="https://example.test/v0.1.0")
    legacy = {
        "profile": "tabular-data-package",
        "name": "tatar-names",
        "resources": [
            {
                "name": "identities",
                "path": "identities.csv",
                "format": "csv",
                "schema": {"path": "../../schemas/identities.schema.json"},
            }
        ],
    }
    (tmp_path / "datapackage.json").write_text(json.dumps(legacy), encoding="utf-8")

    errors, skipped = metadata.validate_metadata(tmp_path)

    assert not skipped
    assert errors
    assert all("datapackage.json" in error for error in errors)


def test_validate_metadata_flags_legacy_croissant(tmp_path: Path) -> None:
    pytest.importorskip("mlcroissant")
    write_release_fixture(tmp_path)
    metadata.write_datapackage(tmp_path, dataset_url="https://example.test/v0.1.0", version="0.1.0")
    legacy = {"@context": "https://schema.org/", "@type": "Dataset", "name": "Tatar Names"}
    (tmp_path / "croissant.json").write_text(json.dumps(legacy), encoding="utf-8")

    errors, skipped = metadata.validate_metadata(tmp_path)

    assert not skipped
    assert errors
    assert all("croissant.json" in error for error in errors)


def test_validate_metadata_passes_on_generated_release(tmp_path: Path) -> None:
    pytest.importorskip("frictionless")
    pytest.importorskip("mlcroissant")
    write_release_fixture(tmp_path)
    metadata.write_croissant(tmp_path, date_published="2026-10-20T00:00:00Z", dataset_url="https://example.test/v0.1.0")
    metadata.write_datapackage(tmp_path, dataset_url="https://example.test/v0.1.0", version="0.1.0")

    errors, skipped = metadata.validate_metadata(tmp_path)

    assert errors == []
    assert skipped == []
