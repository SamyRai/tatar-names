# Transliteration

The toolkit includes small deterministic transliterators:

- `ru_cyrl_to_latn_mvd_doc`: Russian Cyrillic to Latin, passport-style enough for candidate generation.
- `tt_cyrl_to_tt_latn_rt2013`: Tatar Cyrillic to Latin (see the caveat below).

Rules live in YAML under `rules/` and are loaded by named profile. These rules are intended for resolver candidates and release forms. They are not a legal transliteration authority.

## `tt_cyrl_to_tt_latn_rt2013` is a lossy ASCII search fold, not the legal annex

Despite its id, this profile does not implement the RT-2013 legal annex. It is a candidate-generation map that folds Cyrillic input to ASCII search keys, and the fold is lossy in two verified ways:

- Distinct Tatar letters collapse onto the same ASCII letter: ә/а → a, ө/о → o, ү/у → u, ң/н → n. The output cannot distinguish the collapsed letters.
- Letters whose annex values depend on surrounding context (the в/г/к pairs) are folded to one fixed letter each.

The map also deviates from the annex letter values in 9 places (the individual values are not listed here). The profile id is historical. Separating a legal-annex profile from this search profile is planned contract work; until that lands, treat `tt_cyrl_to_tt_latn_rt2013` output as search candidates only, never as legal transliteration.

## Profile contracts

`transliterate.profiles()` returns the declared contract of every profile as a `ProfileContract` (`profile_id`, `purpose`, `lossy`, `legal_authority`, `notes`); `available_profiles()` returns the ids of these contracts.

| Profile id | Purpose | Lossy | Legal authority | Intended use |
| --- | --- | --- | --- | --- |
| `tt_cyrl_to_tt_latn_rt2013` | `search_candidate` | yes | no | ASCII search keys for resolver candidates; see the lossy-fold section above for the collapse pairs and annex deviations. |
| `ru_cyrl_to_latn_mvd_doc` | `documentary_candidate` | yes | no | Passport-style documentary candidates; multi-letter approximations (kh, ts, shch) are approximations, not exact values. |

Neither profile is a legal transliteration authority, as stated above; the contracts make that a declared property of the API rather than a docs-only caveat.
