from __future__ import annotations

from tatar_names.data import default_release_dir, default_source_dir
from tatar_names.pipeline import (
    build_release_rows,
    validate_release,
    validate_source,
    write_csv_table,
    write_metadata,
)


def main() -> None:
    source_dir = default_source_dir()
    release_dir = default_release_dir()

    source_errors = validate_source(source_dir)
    if source_errors:
        raise SystemExit("Source validation failed:\n" + "\n".join(f"- {error}" for error in source_errors))

    rows = build_release_rows(source_dir)
    write_csv_table(
        release_dir / "identities.csv",
        rows["identities"],
        [
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
        ],
    )
    write_csv_table(
        release_dir / "forms.csv",
        rows["forms"],
        [
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
        ],
    )
    write_csv_table(
        release_dir / "relations.csv",
        rows["relations"],
        [
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
        ],
    )
    write_csv_table(
        release_dir / "review_queue.csv",
        rows["review_queue"],
        [
            "review_id",
            "subject_kind",
            "subject_id",
            "queue_reason",
            "suggested_relation",
            "source_id",
            "evidence_id",
            "notes",
        ],
    )
    write_csv_table(
        release_dir / "aliases.csv",
        rows["aliases"],
        [
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
        ],
    )

    obsolete_release_files = ["names.csv"]
    for filename in obsolete_release_files:
        path = release_dir / filename
        if path.exists():
            path.unlink()

    release_errors = validate_release(release_dir)
    if release_errors:
        raise SystemExit("Release validation failed:\n" + "\n".join(f"- {error}" for error in release_errors))
    write_metadata(release_dir)


if __name__ == "__main__":
    main()
