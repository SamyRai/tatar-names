# Dataset

## Summary

Tatar Names is a source-first dataset for auditable Tatar, Russian, and Latin name matching. It models name identities, concrete forms, and explicit relations separately so downstream systems can inspect provenance instead of relying on opaque fuzzy matching.

## Repository Model

The repository treats `data/source/*.csv` as the authoritative working dataset:

1. `entities.csv` stores canonical lexical entities and stable IDs.
2. `attestations.csv` stores source-backed spellings and transliterations tied to those entities.
3. `excluded_entities.csv` preserves generated formations, incomplete rows, and other records that are intentionally kept out of the clean release while still remaining in the repo for review.

The build step materializes `data/release/*.csv` from that source layer:

1. `identities.csv` stores canonical name identities and context-specific primary forms.
2. `forms.csv` stores concrete spellings and transliterations with explicit role and merge semantics.
3. `relations.csv` stores relations between names and forms, including official pairs, script variants, and hard negatives.
4. `review_queue.csv` stores structured review work for weak evidence and excluded rows.
5. `aliases.csv` stores constrained compatibility lookup spellings derived after relation semantics are applied.

The mental model is:

- `name_identity`: the entity being resolved.
- `name_form`: a specific writing or transliteration of that entity.
- `name_relation`: evidence-backed linkage or non-linkage between identities and forms.

## Intended Uses

- Name normalization in genealogical, archival, and civil-record systems.
- Candidate generation for Tatar, Russian, and Latin spelling variants.
- Safety-aware merge decisions where `merge_policy` must be honored separately from string similarity.
- Regression testing for transliteration and alias-resolution logic.

## Not Intended For

- Identity verification by itself.
- Inferring ethnicity, religion, nationality, or other protected attributes.
- Automatic record merges without human review.

## Data Fields and Provenance

Source and release tables are validated against JSON Schema contracts in `schemas/`. Provenance is retained through `source_id`, row/evidence references in the source and release tables, and BibTeX entries in `bibliography.bib`.

Key release semantics:

- `form_role` distinguishes official Tatar, official Russian or russified primary, transliteration, passport Latin, and observed common forms.
- `identity_status` distinguishes canonical, variant, and alias forms.
- `merge_policy` is the operational control plane for downstream merge behavior:
  - `auto_merge`
  - `candidate_only`
  - `never_merge`
  - `review_required`
- `relation` is descriptive evidence, not by itself permission to merge.

Closeness levels used by the release model:

1. Exact same form
2. Same name, different script/transliteration
3. Official Tatar-Russian pair
4. Related but not safe to merge automatically
5. Near-confusable but distinct

The Python SDK build command validates the source and release CSVs and refreshes release metadata files such as:

- `data/release/datapackage.json`
- `data/release/croissant.json`

## Recommended Use Pattern

Use the data to generate ranked candidates from identities and forms, then apply `merge_policy` before any downstream merge decision. Confidence values describe matching provenance and release confidence, not real-world frequency. Patronymics and other deterministic formations should be generated on demand through SDK helpers rather than treated as stored canonical identities.
