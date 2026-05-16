# Dataset

## Summary

Tatar Names is a source-first dataset for auditable Tatar, Russian, and Latin name matching. It separates curated lexical entities, source-backed attestations, preserved exclusions under review, and generated release exports so downstream systems can inspect provenance instead of relying on opaque fuzzy matching.

## Repository Model

The repository treats `data/source/*.csv` as the authoritative working dataset:

1. `entities.csv` stores canonical lexical entities and stable IDs.
2. `attestations.csv` stores source-backed spellings and transliterations tied to those entities.
3. `excluded_entities.csv` preserves generated formations, incomplete rows, and other records that are intentionally kept out of the clean release while still remaining in the repo for review.

The build step materializes `data/release/*.csv` from that source layer:

1. `names.csv` stores canonical lexical identities only.
2. `forms.csv` stores unambiguous source-backed lexical spellings and transliterations.
3. `aliases.csv` stores constrained compatibility lookup spellings derived from safe release forms.

## Intended Uses

- Name normalization in genealogical, archival, and civil-record systems.
- Candidate generation for Tatar, Russian, and Latin spelling variants.
- Regression testing for transliteration and alias-resolution logic.

## Not Intended For

- Identity verification by itself.
- Inferring ethnicity, religion, nationality, or other protected attributes.
- Automatic record merges without human review.

## Data Fields and Provenance

Source and release tables are validated against JSON Schema contracts in `schemas/`. Provenance is retained through `source_id`, row/evidence references in the source and release tables, and BibTeX entries in `bibliography.bib`.

The Python SDK build command validates the source and release CSVs and refreshes release metadata files such as:

- `data/release/datapackage.json`
- `data/release/croissant.json`

## Recommended Use Pattern

Use the data to generate ranked candidates from lexical entities only. Confidence values describe matching provenance and release confidence, not real-world frequency. Patronymics and other deterministic formations should be generated on demand through SDK helpers rather than treated as stored canonical entities.
