# Regression baseline (v0.1.0)

Frozen before the first correctness fixes so every later change has a reference
point. Reproduce with:

```bash
cd sdks/python
uv run python benchmarks/bench_baseline.py
uv run pytest  # wall time, see below
```

- Commit: `4cc356b` (clean tree). Measured: 2026-10-20, Darwin arm64, CPython 3.14.5 (CI runs 3.12; treat all numbers as host-specific).
- The 2026-10 code review separately measured the audit-embedded relation-coverage pass at 122.05 s on the same commit; the standalone scan below is the same computation without the surrounding table loads.

## Hot-path timings

| Path | Result |
| --- | --- |
| `resolve()` exact query, median of 3 | 1.07 s |
| `resolve()` exact query, max | 1.12 s |
| `resolve()` alias branch, median of 3 | 1.20 s |
| Relation-coverage scan (identities × relations) | 68.0 s standalone |
| `pytest` full suite (23 tests) | recorded in the table below on each run |

Every `resolve()` call re-parses all release tables (~224k rows / ~30 MB); the
index work planned for the resolver phase targets warm steady-state p95 < 10 ms
for exact lookups, measured against this baseline with repeated samples.

## Row counts and table hashes

| Table | Rows | SHA-256 |
| --- | --- | --- |
| source/entities.csv | 11,301 | `7192b477342c8175daad91edaccb68d9bd6969a14ed9ed1b99a29fbc13084fbd` |
| source/attestations.csv | 64,822 | `ae5bd463df5f3f023c881a255e1fd4abdece1af01d4047f31ba0e79c8c06b97f` |
| source/excluded_entities.csv | 6,939 | `1a83376bfc2c58a34aafc923c99ed961b8a591b2f5fb0a27aaa18bf26768092d` |
| release/identities.csv | 11,301 | `827572d778e2002ab38a2415a4dbb9fce595367601d511e804716a2934762b2b` |
| release/forms.csv | 53,531 | `a215e7a6edbac835dfc17d695196c25d71c3143068f47b35c872e7c48558d013` |
| release/relations.csv | 154,696 | `516741a021b7fc407eee096fdb0dc7d2a4558ab02d2107fc994b744c0e916640` |
| release/review_queue.csv | 6,951 | `3d054ea11933af08427af81be0eb9e86f31f7ece5f5f7a58bd4df1e24510a8a1` |
| release/aliases.csv | 8 | `79cc2a49c0651d4a6243596427ae2d4f9c2ba7b4e82ebaacf702d9e0679dc55b` |

`release_sha256` values pin the pre-fix release bytes. The first correctness
wave intentionally changes `rules/` behavior and `review_queue.csv` content;
`forms.csv`, `relations.csv`, and `identities.csv` are expected to stay
byte-identical through that wave — any drift there is a regression, not a fix.

## Known-defect reference

The defect list this baseline is judged against is the 2026-10 deep-review
register (validator crash, patronymic stems, passport hard sign, rt2013
labeling, shared-spelling loss, superseded-attestation loss). Re-run
`bench_baseline.py` after each fix wave and extend the table above with dated
rows rather than overwriting history.
