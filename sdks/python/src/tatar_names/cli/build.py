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
        release_dir / "names.csv",
        rows["names"],
        [
            "name_id",
            "gender",
            "canonical_tt_cyrl",
            "canonical_ru_cyrl",
            "canonical_tt_latn",
            "canonical_ru_latn",
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
            "profile",
            "is_canonical",
            "confidence",
            "source_id",
            "evidence_id",
        ],
    )
    write_csv_table(
        release_dir / "aliases.csv",
        rows["aliases"],
        [
            "alias_id",
            "name_id",
            "alias",
            "script",
            "language_tag",
            "alias_type",
            "method",
            "confidence",
            "source_id",
            "rule_id",
        ],
    )

    release_errors = validate_release(release_dir)
    if release_errors:
        raise SystemExit("Release validation failed:\n" + "\n".join(f"- {error}" for error in release_errors))
    write_metadata(release_dir)


if __name__ == "__main__":
    main()
