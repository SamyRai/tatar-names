# Transliteration

The toolkit includes small deterministic transliterators:

- `ru_cyrl_to_latn_mvd_doc`: Russian Cyrillic to Latin, passport-style enough for candidate generation.
- `tt_cyrl_to_tt_latn_rt2013`: Tatar Cyrillic to Latin using Tatar-specific letters.

Rules live in YAML under `rules/` and are loaded by named profile. These rules are intended for resolver candidates and release forms. They are not a legal transliteration authority.
