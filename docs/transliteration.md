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
