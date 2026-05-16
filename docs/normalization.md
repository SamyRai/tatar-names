# Normalization

Normalization is split into two levels:

- Safe normalization: Unicode NFKC, lowercase, trim, punctuation cleanup, whitespace collapse, and `ё` to `е`.
- Candidate-only normalization: removes marks such as `ь` and `ъ`, folds `й` to `и`, and removes spaces or hyphens.

Only safe normalization should be used for exact lookup. Candidate-only keys are lossy and must not be used as proof that two names are the same.

The `forms` table may contain ambiguous generated forms. `aliases` is the manually constrained compatibility export for callers that need one normalized form to point to one identity.
