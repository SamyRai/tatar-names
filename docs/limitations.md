# Limitations

- The bootstrap release inherits the quality and scope of the existing structured source material.
- Source row and page references are not yet complete for every record.
- Generated Latin aliases and weak common variants should be reviewed before being treated as official.
- Some historical rows are preserved in `data/source/excluded_entities.csv` because they are generated formations, incomplete records, or unresolved review cases and are intentionally omitted from the clean release.
- Russian forms can be socially primary without replacing Tatar canonical forms; callers should not collapse them into one display field.
- Fuzzy matching can still produce dangerous false positives; use `merge_policy`, `relation`, and provenance rather than assuming similar spellings are equivalent.
