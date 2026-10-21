import csv
from pathlib import Path

from tatar_names.pipeline import build_release_rows, validate_source


ROOT = Path(__file__).resolve().parents[3]

ENTITY_FIELDS = [
    "entity_id",
    "entity_type",
    "gender",
    "canonical_tt_cyrl",
    "canonical_ru_cyrl",
    "canonical_tt_latn",
    "canonical_ru_latn",
    "source_id",
    "source_row",
    "status",
    "notes",
    "is_lexical_exception",
]
ATTESTATION_FIELDS = [
    "attestation_id",
    "entity_id",
    "form",
    "script",
    "language_tag",
    "form_kind",
    "profile",
    "is_canonical",
    "confidence",
    "source_id",
    "evidence_id",
]
EXCLUDED_FIELDS = [
    "original_name_id",
    "reason",
    "gender",
    "canonical_tt_cyrl",
    "canonical_ru_cyrl",
    "canonical_tt_latn",
    "canonical_ru_latn",
    "source_id",
    "source_row",
    "status",
    "notes",
]


def borrowed_source_id() -> str:
    path = ROOT / "data" / "source" / "entities.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle))["source_id"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def entity_row(entity_id: str, tt_cyrl: str, tt_latn: str, source_row: str) -> dict[str, str]:
    return {
        "entity_id": entity_id,
        "entity_type": "given",
        "gender": "male",
        "canonical_tt_cyrl": tt_cyrl,
        "canonical_ru_cyrl": tt_cyrl,
        "canonical_tt_latn": tt_latn,
        "canonical_ru_latn": tt_latn,
        "source_id": borrowed_source_id(),
        "source_row": source_row,
        "status": "active",
        "notes": "",
        "is_lexical_exception": "false",
    }


def attestation_row(
    attestation_id: str,
    entity_id: str,
    form: str,
    evidence_id: str,
    *,
    script: str = "Cyrl",
    language_tag: str = "tt-Cyrl",
    form_kind: str = "canonical",
    profile: str = "tt_original",
    is_canonical: str = "true",
    confidence: str = "1.00",
) -> dict[str, str]:
    return {
        "attestation_id": attestation_id,
        "entity_id": entity_id,
        "form": form,
        "script": script,
        "language_tag": language_tag,
        "form_kind": form_kind,
        "profile": profile,
        "is_canonical": is_canonical,
        "confidence": confidence,
        "source_id": borrowed_source_id(),
        "evidence_id": evidence_id,
    }


def make_source_dir(
    tmp_path: Path,
    entities: list[dict[str, str]],
    attestations: list[dict[str, str]],
) -> Path:
    source_dir = tmp_path / "data" / "source"
    (tmp_path / "bibliography.bib").write_text(
        f"@misc{{{borrowed_source_id()},\n  title = {{fixture source}}\n}}\n",
        encoding="utf-8",
    )
    write_csv(source_dir / "entities.csv", ENTITY_FIELDS, entities)
    write_csv(source_dir / "attestations.csv", ATTESTATION_FIELDS, attestations)
    write_csv(source_dir / "excluded_entities.csv", EXCLUDED_FIELDS, [])
    return source_dir


def test_validate_source_reports_unknown_entity_without_crashing(tmp_path: Path) -> None:
    source_dir = make_source_dir(
        tmp_path,
        [entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001")],
        [
            attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001"),
            attestation_row(
                "at_0000002",
                "ttn_999999",
                "Акмал",
                "ev_0000002",
                language_tag="ru-Cyrl",
                profile="ru_adaptation",
                is_canonical="false",
            ),
        ],
    )

    errors = validate_source(source_dir)

    assert errors == ["attestation at_0000002 references unknown entity_id ttn_999999"]


def test_build_release_rows_emits_shared_spelling_candidates(tmp_path: Path) -> None:
    source_dir = make_source_dir(
        tmp_path,
        [
            entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001"),
            entity_row("ttn_000002", "Камал", "Kamal", "ev_0000002"),
        ],
        [
            attestation_row("at_0000001", "ttn_000001", "Камал", "ev_0000001"),
            attestation_row("at_0000002", "ttn_000002", "Камал", "ev_0000002"),
        ],
    )

    rows = build_release_rows(source_dir)

    forms = {row["form_id"]: row for row in rows["forms"]}
    assert set(forms) == {"f_0000001", "f_0000002"}
    assert forms["f_0000001"]["name_id"] == "ttn_000001"
    assert forms["f_0000002"]["name_id"] == "ttn_000002"
    for row in forms.values():
        assert row["form"] == "Камал"
        assert row["identity_status"] == "ambiguous_candidate"
        assert row["merge_policy"] == "review_required"
    shared = [row for row in rows["review_queue"] if row["queue_reason"] == "shared_spelling_group"]
    assert {row["subject_id"] for row in shared} == {"at_0000001", "at_0000002"}
    assert {row["evidence_id"] for row in shared} == {"ev_0000001", "ev_0000002"}
    for row in shared:
        assert row["subject_kind"] == "form"
        assert row["suggested_relation"] == "review_candidate"
        assert row["source_id"] == borrowed_source_id()
        assert "Камал" in row["notes"]
        assert "ttn_000001" in row["notes"]
        assert "ttn_000002" in row["notes"]


def test_build_release_rows_keeps_superseded_attestation_evidence(tmp_path: Path) -> None:
    source_dir = make_source_dir(
        tmp_path,
        [entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001")],
        [
            attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001"),
            attestation_row(
                "at_0000002",
                "ttn_000001",
                "Акмал",
                "ev_0000002",
                form_kind="observed_variant",
                profile="common_variant",
                is_canonical="false",
                confidence="0.85",
            ),
        ],
    )

    rows = build_release_rows(source_dir)

    assert [row["form_id"] for row in rows["forms"]] == ["f_0000001"]
    assert rows["forms"][0]["name_id"] == "ttn_000001"
    superseded = [row for row in rows["review_queue"] if row["queue_reason"] == "superseded_attestation"]
    assert len(superseded) == 1
    row = superseded[0]
    assert row["subject_kind"] == "form"
    assert row["subject_id"] == "at_0000002"
    assert row["suggested_relation"] == "review_candidate"
    assert row["source_id"] == borrowed_source_id()
    assert row["evidence_id"] == "ev_0000002"
    assert "Акмал" in row["notes"]
    assert "superseded_by=at_0000001" in row["notes"]


def test_build_release_rows_marks_normalized_shared_spelling_across_tags(tmp_path: Path) -> None:
    # Same letters under different language tags share the resolver's
    # normalized key, so both rows must be marked ambiguous even though no
    # exact (form, script, language_tag) triple is shared.
    source_dir = make_source_dir(
        tmp_path,
        [
            entity_row("ttn_000001", "Алиш", "Alish", "ev_0000001"),
            entity_row("ttn_000002", "Алишев", "Alishev", "ev_0000002"),
        ],
        [
            attestation_row("at_0000001", "ttn_000001", "Алиш", "ev_0000001"),
            attestation_row(
                "at_0000002",
                "ttn_000002",
                "Алиш",
                "ev_0000002",
                language_tag="ru-Cyrl",
                profile="ru_adaptation",
            ),
        ],
    )

    rows = build_release_rows(source_dir)

    forms = {row["form_id"]: row for row in rows["forms"]}
    assert set(forms) == {"f_0000001", "f_0000002"}
    assert forms["f_0000001"]["script"] == "Cyrl" and forms["f_0000002"]["script"] == "Cyrl"
    assert {forms["f_0000001"]["language_tag"], forms["f_0000002"]["language_tag"]} == {"tt-Cyrl", "ru-Cyrl"}
    for row in forms.values():
        assert row["identity_status"] == "ambiguous_candidate"
        assert row["merge_policy"] == "review_required"
