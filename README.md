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
  - config_name: names
    data_files: data/release/names.csv
  - config_name: forms
    data_files: data/release/forms.csv
  - config_name: aliases
    data_files: data/release/aliases.csv
---

# Tatar Names

Open data and a small resolver toolkit for Tatar, Russian, and Latin name forms.

The repository is organized around curated source tables, generated release artifacts, and a small Python SDK:

- `data/source/`: authoritative lexical entities, attestations, and preserved exclusions under review.
- `data/release/`: generated clean release CSV tables.
- `sdks/python/src/tatar_names/`: normalization, transliteration, and alias-resolution helpers.
- `schemas/`: JSON Schema contracts for source and release tables.
- `rules/`: normalization and transliteration rule tables used by the SDK.
- `docs/`: dataset, normalization, transliteration, and limitations documentation.

## Source Tables

- `data/source/entities.csv`: canonical lexical name entities with stable IDs.
- `data/source/attestations.csv`: source-backed lexical spellings and transliterations.
- `data/source/excluded_entities.csv`: preserved patronymics, incomplete rows, and review cases kept out of the clean release.

## Release Tables

- `data/release/names.csv`: generated canonical lexical identities with stable IDs.
- `data/release/forms.csv`: generated source-backed and unambiguous lexical spellings.
- `data/release/aliases.csv`: generated compatibility lookup spellings from safe release forms.

The working source of truth is the CSV source set under `data/source/`. Release tables and metadata are generated from source. Patronymics and other deterministic formations are supported through the SDK but are not stored as release entities.

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
