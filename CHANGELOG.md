# Changelog

## Unreleased

- Ambiguity (TN-15, ADR-002/ADR-005): a spelling attested for several identities is now compiled as an explicit multi-candidate form set — every candidate is released with `identity_status=ambiguous_candidate` and `merge_policy=review_required` instead of the whole group being routed to review and dropped; `validate_release` enforces the marking in both directions (shared spellings must be marked, `ambiguous_candidate` must actually be shared).
- Resolver API (TN-22): new `Resolver.from_package()` / `Resolver.from_path()` with `lookup(value, entity_type=..., language_hint=..., mode=...)` returning an explicit `not_found` / `unique_candidate` / `ambiguous` status. Each candidate carries the stable name id, matched form, script/language, entity type, match type, merge policy, source reference, and near-confusable warnings. Ambiguity is never resolved by ranking; hints narrow the candidate set and never pick a winner. The module-level `resolve()` keeps its previous output for existing release data as a compatibility adapter.
- Compiler internals (TN-17): mechanically derived same-identity form-to-form edges remain in the `relations.csv` backward-compatible view but no longer enter the resolver's internal index, which now loads only independently evidenced relations.

## 0.2.0 — 2026-10-21

- Correctness: patronymic stems follow the standard soft-stem rule for -ий bases (Юрий → Юрьевич) with Latin derivation kept in parity; all-caps transliteration renders multi-letter maps uppercase (ЦАРЕВ → TSAREV); the passport map transliterates ъ as `ie` (ICAO Doc 9303 Part 3); `validate_source` reports unknown attestation entities instead of crashing.
- Data safety: exact spellings attested for several identities and superseded supporting attestations are now preserved as review-queue rows instead of being silently dropped (review_queue grew 6,951 → 18,242 rows; forms/relations/identities content unchanged).
- Contracts: the JSON Schemas are the single authority — Frictionless Table Schemas, the validation constants, and package metadata fields are generated from them (`python -m tatar_names.codegen`, drift-checked in CI); normalization levels (canonical / lookup / candidate-search) and transliteration profile contracts (purpose, lossiness, legal-authority) are explicit API.
- Semantics: the resolver's merge recommendation is now `form_match_auto_merge` with a fixed advisory string — a lexical form match no longer implies person-merge permission.
- Compiler: relation ids are content-derived 12-hex digests (stable across dataset versions; genuine collisions fail the build); the build publishes atomically through a validated staging directory.
- Performance: the resolver reads from a cached immutable index — warm exact lookups measure ~1 ms p95 (was ~1.07 s per call re-reading ~30 MB); the relation-coverage audit is linear (~122 s → ~3.6 s end-to-end).
- Packaging: rule tables ship inside the wheel and load via `importlib.resources`; the corpus stays a release asset; build backend pinned to `uv_build>=0.13.4,<0.14`.

## 0.1.0

- Initial public release.
- Added the release CSV dataset under `data/release/`.
- Added the Python SDK for normalization, transliteration, validation, and alias resolution.
- Added release metadata, source attribution, and repository documentation.
- Added automated CI and release asset packaging.
