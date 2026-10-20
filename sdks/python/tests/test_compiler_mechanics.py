from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from tatar_names.cli import build as build_cli
from tatar_names.pipeline import (
    _assign_relation_ids,
    _relation_base_digest,
    _relation_canonical_key,
    _record_relation_payload,
    build_release_rows,
    write_csv_table,
)

from test_pipeline_data_safety import (
    ATTESTATION_FIELDS,
    ENTITY_FIELDS,
    EXCLUDED_FIELDS,
    attestation_row,
    borrowed_source_id,
    entity_row,
    make_source_dir as write_source_fixture,
)

RELATION_FIELDS = [
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
]
RELATION_ID_PATTERN = re.compile(r"^rel_[0-9a-f]{12}$")


def make_source_dir(
    base: Path,
    entities: list[dict[str, str]],
    attestations: list[dict[str, str]],
) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    return write_source_fixture(base, entities, attestations)


def simple_fixture(base: Path) -> Path:
    return make_source_dir(
        base,
        [entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001")],
        [attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001")],
    )


def relations_csv_bytes(source_dir: Path, work_dir: Path) -> bytes:
    rows = build_release_rows(source_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "relations.csv"
    write_csv_table(target, rows["relations"], RELATION_FIELDS)
    return target.read_bytes()


def test_relation_ids_match_schema_pattern(tmp_path: Path) -> None:
    source_dir = simple_fixture(tmp_path / "source")

    rows = build_release_rows(source_dir)

    assert rows["relations"]
    for row in rows["relations"]:
        assert RELATION_ID_PATTERN.fullmatch(row["relation_id"])


def test_relation_ids_identical_across_repeated_builds(tmp_path: Path) -> None:
    source_dir = simple_fixture(tmp_path / "source")

    first = relations_csv_bytes(source_dir, tmp_path / "first")
    second = relations_csv_bytes(source_dir, tmp_path / "second")

    assert first == second


def test_relation_ids_survive_input_row_reordering(tmp_path: Path) -> None:
    entities = [
        entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001"),
        entity_row("ttn_000002", "Камал", "Kamal", "ev_0000002"),
    ]
    attestations = [
        attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001"),
        attestation_row(
            "at_0000002",
            "ttn_000001",
            "Акбар",
            "ev_0000002",
            script="Latn",
            language_tag="tt-Latn",
            profile="tt_cyrl_to_tt_latn_rt2013",
            confidence="0.95",
        ),
        attestation_row("at_0000003", "ttn_000002", "Камал", "ev_0000003"),
    ]

    forward_dir = make_source_dir(tmp_path / "forward", entities, attestations)
    reversed_dir = make_source_dir(tmp_path / "reversed", entities, list(reversed(attestations)))

    forward_bytes = relations_csv_bytes(forward_dir, tmp_path / "forward_out")
    reversed_bytes = relations_csv_bytes(reversed_dir, tmp_path / "reversed_out")

    assert forward_bytes == reversed_bytes


def _find_colliding_canonical_keys() -> tuple[str, str]:
    key = _relation_canonical_key(
        "name", "ttn_000001", "form", "f_0000001", "same_name_official_pair", "source_attestation"
    )
    seen = {key: _relation_base_digest(key)}
    counter = 0
    while True:
        counter += 1
        key = _relation_canonical_key(
            "name", f"ttn_{counter % 900000 + 100000:06d}", "form", f"f_{counter % 9000000 + 1000000:07d}",
            "same_name_official_pair", f"source_attestation_{counter}",
        )
        digest = _relation_base_digest(key)
        for existing_key, existing_digest in seen.items():
            if existing_digest == digest:
                return existing_key, key
        seen[key] = digest


def test_assign_relation_ids_resolves_digest_collisions_deterministically() -> None:
    key_a, key_b = _find_colliding_canonical_keys()
    assert key_a != key_b
    assert _relation_base_digest(key_a) == _relation_base_digest(key_b)

    payload_a = {
        "left_kind": "name",
        "left_id": "ttn_000001",
        "right_kind": "form",
        "right_id": "f_0000001",
        "relation": "same_name_official_pair",
        "merge_policy": "auto_merge",
        "confidence": "1.00",
        "evidence_type": "source_attestation",
        "source_id": "src",
        "evidence_id": "ev_1",
        "notes": "a",
    }
    payload_b = dict(payload_a, notes="b")

    forward = _assign_relation_ids({key_a: payload_a, key_b: payload_b})
    backward = _assign_relation_ids({key_b: payload_b, key_a: payload_a})

    forward_by_notes = {row["notes"]: row["relation_id"] for row in forward}
    backward_by_notes = {row["notes"]: row["relation_id"] for row in backward}
    assert forward_by_notes == backward_by_notes
    assert len(set(forward_by_notes.values())) == 2
    for relation_id in forward_by_notes.values():
        assert RELATION_ID_PATTERN.fullmatch(relation_id)


def test_record_relation_payload_dedups_identical_content() -> None:
    store: dict[str, dict[str, str]] = {}
    _record_relation_payload(store, "key", {"notes": "same"})
    _record_relation_payload(store, "key", {"notes": "same"})

    assert list(store) == ["key"]


def test_record_relation_payload_raises_on_conflicting_content() -> None:
    store: dict[str, dict[str, str]] = {}
    _record_relation_payload(store, "key", {"notes": "first"})

    with pytest.raises(ValueError, match="conflicting duplicate relation content"):
        _record_relation_payload(store, "key", {"notes": "second"})


def test_failed_release_validation_leaves_live_release_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shared spelling group: passes source validation but fails release validation
    # because neither name ends up with an auto-merge form.
    entities = [
        entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001"),
        entity_row("ttn_000002", "Камал", "Kamal", "ev_0000002"),
    ]
    attestations = [
        attestation_row("at_0000001", "ttn_000001", "Камал", "ev_0000001"),
        attestation_row("at_0000002", "ttn_000002", "Камал", "ev_0000002"),
    ]
    source_dir = make_source_dir(tmp_path, entities, attestations)

    release_dir = tmp_path / "data" / "release"
    release_dir.mkdir(parents=True)
    sentinel = release_dir / "relations.csv"
    sentinel.write_text("relation_id,notes\nrel_SENTINEL,do not touch\n", encoding="utf-8")

    monkeypatch.setattr(build_cli, "default_source_dir", lambda: source_dir)
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: release_dir)

    with pytest.raises(SystemExit, match="Release validation failed"):
        build_cli.main()

    assert sentinel.read_text(encoding="utf-8") == "relation_id,notes\nrel_SENTINEL,do not touch\n"
    assert not (release_dir.parent / ".release-staging").exists()


def test_successful_build_replaces_release_and_removes_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = simple_fixture(tmp_path)

    release_dir = tmp_path / "data" / "release"
    release_dir.mkdir(parents=True)
    for filename in ("identities.csv", "forms.csv", "relations.csv", "review_queue.csv", "aliases.csv"):
        (release_dir / filename).write_text("stale\n", encoding="utf-8")

    monkeypatch.setattr(build_cli, "default_source_dir", lambda: source_dir)
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: release_dir)

    build_cli.main()

    with (release_dir / "relations.csv").open(newline="", encoding="utf-8") as handle:
        relations = list(csv.DictReader(handle))
    assert [row["left_id"] for row in relations] == ["ttn_000001"]
    assert all(RELATION_ID_PATTERN.fullmatch(row["relation_id"]) for row in relations)
    datapackage = json.loads((release_dir / "datapackage.json").read_text(encoding="utf-8"))
    assert datapackage["name"] == "tatar-names"
    assert (release_dir / "croissant.json").exists()
    assert not (release_dir.parent / ".release-staging").exists()
