# Normalization

Normalization produces keys at three explicit levels, named by
`tatar_names.normalize.Level` and dispatched by `normalize_key(name, level)`.
Each level has a different contract; callers must pick the level whose
guarantees they rely on.

| Level | Implementation | Preserves | Folds |
| --- | --- | --- | --- |
| `CANONICAL` | NFC normalize only | the recorded form itself: case, letters, punctuation, whitespace | nothing except Unicode composition (e.g. `Е` + combining diaeresis → `Ё`) |
| `LOOKUP` | `safe()` | distinct characters after cleanup: case-insensitive, single-spaced, hyphen-class unified to `-` | NFKC, lowercase, trim, `ё` → `е`, punctuation removed, whitespace collapsed |
| `CANDIDATE_SEARCH` | `soft_key()` | coarse shape for candidate generation | everything LOOKUP folds, plus `й` → `и`, `ь`/`ъ`/apostrophes/quotes removed, spaces and hyphens removed |

Guarantees:

- LOOKUP keys are stable across dataset versions: a record's lookup key does not change when the dataset is re-released. Only LOOKUP may be used for exact lookup.
- CANDIDATE_SEARCH keys are lossy and allowed to change with rule releases; they must never be used as proof that two names are the same.
- Fuzzy matching is not a normalization level. It happens in the resolver on top of candidate keys; `normalize_key` never returns fuzzy results.

The `forms` table may contain ambiguous generated forms. `aliases` is the manually constrained compatibility export for callers that need one normalized form to point to one identity.
