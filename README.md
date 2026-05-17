---
license: cc-by-4.0
language:
  - tt
  - ru
pretty_name: Tatar Names
tags:
  - names
  - tatar
  - russian
  - transliteration
  - alias-resolution
  - onomastics
configs:
  - config_name: identities
    data_files: data/release/identities.csv
  - config_name: forms
    data_files: data/release/forms.csv
  - config_name: relations
    data_files: data/release/relations.csv
  - config_name: review_queue
    data_files: data/release/review_queue.csv
  - config_name: aliases
    data_files: data/release/aliases.csv
---

# Tatar Names

Open data and a relation-aware resolver toolkit for Tatar, Russian, and Latin name identities and forms.

The repository is organized around curated source tables, generated release artifacts, and a small Python SDK:

- `data/source/`: authoritative lexical entities, attestations, and preserved exclusions under review.
- `data/release/`: generated clean release CSV tables.
- `sdks/python/src/tatar_names/`: normalization, transliteration, audit, and relation-aware resolution helpers.
- `schemas/`: JSON Schema contracts for source and release tables.
- `rules/`: normalization and transliteration rule tables used by the SDK.
- `docs/`: dataset, normalization, transliteration, and limitations documentation.

## Source Tables

- `data/source/entities.csv`: canonical lexical name entities with stable IDs.
- `data/source/attestations.csv`: source-backed lexical spellings and transliterations.
- `data/source/excluded_entities.csv`: preserved patronymics, incomplete rows, and review cases kept out of the clean release.

## Release Tables

- `data/release/identities.csv`: generated canonical name identities with stable IDs and context primary forms.
- `data/release/forms.csv`: generated concrete forms with explicit `form_role`, `identity_status`, and `merge_policy`.
- `data/release/relations.csv`: generated name-form and name-name relations, including hard-negative confusables.
- `data/release/review_queue.csv`: generated review backlog for weak evidence, exclusions, and uncovered confusable rules.
- `data/release/aliases.csv`: derived compatibility lookup spellings built after relation semantics are applied.

The working source of truth is the CSV source set under `data/source/`. Release tables and metadata are generated from source. Patronymics and other deterministic formations are supported through the SDK but are not stored as canonical release identities.

## Quickstart

```bash
cd sdks/python
uv sync
uv run tatar-names-build
uv run tatar-names-validate
uv run pytest
uv build
```

```python
from tatar_names import normalize, resolve, transliterate
from tatar_names.formations import generate_patronymic

normalize.safe(" Эльмир! ")
# "эльмир"

transliterate.ru_to_latin("Мухаммет")
# "Mukhammet"

resolve.resolve("Эльмир")
# {"best_match": {...}, "near_misses": [...], "relation_warnings": [...], ...}

generate_patronymic(
    {
        "canonical_tt_cyrl": "Әбелкәрам",
        "canonical_ru_cyrl": "Абелькарам",
        "canonical_tt_latn": "Abelkaram",
        "canonical_ru_latn": "Abelkaram",
    },
    "male",
)
# {"canonical_tt_cyrl": "Әбелкәрам улы", ...}
```

## Verification

The canonical local verification flow is:

```bash
cd sdks/python
uv run pytest
uv build
```

## Documentation

- Dataset overview, methodology, and field guidance: `docs/dataset.md`
- Normalization behavior: `docs/normalization.md`
- Transliteration profiles: `docs/transliteration.md`
- Known limitations and operating constraints: `docs/limitations.md`

## Sources and Attribution

Primary source attribution is kept in `NOTICE` and `bibliography.bib`.

## License

Code is MIT licensed. Dataset tables are released as CC BY 4.0 with attribution to the original source materials described in `NOTICE`.
