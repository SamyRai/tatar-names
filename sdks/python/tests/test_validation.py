import csv
import shutil
from pathlib import Path

from tatar_names.cli.validate import validate_project
from tatar_names.pipeline import build_release_rows, validate_release, validate_source


ROOT = Path(__file__).resolve().parents[3]


def copy_dataset(tmp_path: Path) -> tuple[Path, Path]:
    source = ROOT / "data" / "source"
    release = ROOT / "data" / "release"
    source_target = tmp_path / "source"
    release_target = tmp_path / "release"
    shutil.copytree(source, source_target)
    shutil.copytree(release, release_target)
    return source_target, release_target


def rewrite_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_clean_dataset_validates() -> None:
    assert validate_project() == []


def test_validation_rejects_stored_patronymic_entity(tmp_path: Path) -> None:
    source_dir, release_dir = copy_dataset(tmp_path)
    rows = read_csv(source_dir / "entities.csv")
    rows[0]["canonical_tt_cyrl"] = "Амал улы"
    rows[0]["canonical_ru_cyrl"] = "Амалович"
    rows[0]["canonical_tt_latn"] = "Amal uly"
    rows[0]["canonical_ru_latn"] = "Amalovich"
    rewrite_csv(source_dir / "entities.csv", rows)

    errors = validate_project(source_dir, release_dir)
    assert any("stores generated formation patronymic" in error for error in errors)


def test_validation_rejects_malformed_repetition_in_source(tmp_path: Path) -> None:
    source_dir, _ = copy_dataset(tmp_path)
    rows = read_csv(source_dir / "entities.csv")
    rows[0]["canonical_tt_cyrl"] = "Амал улы улы"
    rewrite_csv(source_dir / "entities.csv", rows)

    assert any("suspicious repetition" in error for error in validate_source(source_dir))


def test_validation_rejects_ambiguous_release_form(tmp_path: Path) -> None:
    _, release_dir = copy_dataset(tmp_path)
    rows = read_csv(release_dir / "forms.csv")
    target_index = next(index for index, row in enumerate(rows) if row["name_id"] != rows[0]["name_id"])
    rows[target_index]["form"] = rows[0]["form"]
    rows[target_index]["script"] = rows[0]["script"]
    rows[target_index]["language_tag"] = rows[0]["language_tag"]
    rewrite_csv(release_dir / "forms.csv", rows)

    assert any("exact release form" in error for error in validate_release(release_dir))


def test_validation_rejects_cross_type_source_alias_candidate(tmp_path: Path) -> None:
    source_dir, _ = copy_dataset(tmp_path)
    entities = read_csv(source_dir / "entities.csv")
    attestations = read_csv(source_dir / "attestations.csv")
    given = next(row for row in entities if row["entity_type"] == "given")
    surname = next(row for row in entities if row["entity_type"] == "surname")
    target = next(row for row in attestations if row["entity_id"] == surname["entity_id"] and row["is_canonical"] == "false")
    target["form"] = "SharedAlias"
    target["script"] = "Latn"
    target["language_tag"] = "ru-Latn"
    other = next(row for row in attestations if row["entity_id"] == given["entity_id"] and row["is_canonical"] == "false")
    other["form"] = "SharedAlias"
    other["script"] = "Latn"
    other["language_tag"] = "ru-Latn"
    rewrite_csv(source_dir / "attestations.csv", attestations)

    assert any("spans multiple entity types" in error for error in validate_source(source_dir))


def test_source_directory_exists_and_relations_release_exists() -> None:
    assert (ROOT / "data" / "source").exists()
    assert (ROOT / "data" / "release" / "relations.csv").exists()


def test_bibliography_exists_and_covers_dataset_sources() -> None:
    bibliography = (ROOT / "bibliography.bib").read_text(encoding="utf-8")
    source = ROOT / "data" / "source"
    release = ROOT / "data" / "release"
    entities = read_csv(source / "entities.csv")
    attestations = read_csv(source / "attestations.csv")
    excluded = read_csv(source / "excluded_entities.csv")
    identities = read_csv(release / "identities.csv")
    forms = read_csv(release / "forms.csv")
    relations = read_csv(release / "relations.csv")
    review_queue = read_csv(release / "review_queue.csv")
    aliases = read_csv(release / "aliases.csv")

    for source_id in {row["source_id"] for row in entities + attestations + excluded + identities + forms + relations + review_queue + aliases}:
        assert f"{{{source_id}," in bibliography or source_id == "confusables_rule"


def test_build_release_rows_adds_official_and_hard_negative_relations() -> None:
    rows = build_release_rows()

    guzel_forms = [row for row in rows["forms"] if row["name_id"] == "ttn_008828"]
    assert any(row["form"] == "Гүзәл" and row["merge_policy"] == "auto_merge" for row in guzel_forms)
    assert any(row["form"] == "Гузель" and row["merge_policy"] == "auto_merge" for row in guzel_forms)
    assert any(
        row["left_kind"] == "name"
        and row["left_id"] == "ttn_008828"
        and row["relation"] in {"same_name_official_pair", "russified_primary_form"}
        for row in rows["relations"]
    )
    assert any(
        row["relation"] == "near_confusable_but_distinct"
        and {row["left_id"], row["right_id"]} == {"ttn_012319", "ttn_030398"}
        for row in rows["relations"]
    )


def test_validation_rejects_relation_with_invalid_kind(tmp_path: Path) -> None:
    _, release_dir = copy_dataset(tmp_path)
    rows = read_csv(release_dir / "relations.csv")
    rows[0]["left_kind"] = "alias"
    rewrite_csv(release_dir / "relations.csv", rows)

    assert any("invalid left_kind" in error for error in validate_release(release_dir))


def test_validation_rejects_relation_missing_merge_policy(tmp_path: Path) -> None:
    _, release_dir = copy_dataset(tmp_path)
    rows = read_csv(release_dir / "relations.csv")
    rows[0]["merge_policy"] = ""
    rewrite_csv(release_dir / "relations.csv", rows)

    assert any("invalid merge_policy" in error for error in validate_release(release_dir))


def test_validation_rejects_auto_merge_on_hard_negative(tmp_path: Path) -> None:
    _, release_dir = copy_dataset(tmp_path)
    rows = read_csv(release_dir / "relations.csv")
    target = next(row for row in rows if row["relation"] == "near_confusable_but_distinct")
    target["merge_policy"] = "auto_merge"
    rewrite_csv(release_dir / "relations.csv", rows)

    assert any("cannot auto_merge near_confusable_but_distinct" in error for error in validate_release(release_dir))
