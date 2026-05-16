# tatar-names Python SDK

Python helpers for the Tatar Names dataset.

The source of truth lives at the repository root under `data/source`, and the clean resolver dataset is generated under `data/release`. The SDK loads release data by default when used from a repo checkout and also accepts an explicit `data_dir` for packaged or external dataset locations.

## Developer Flow

```bash
uv sync
uv run tatar-names-audit
uv run tatar-names-build
uv run pytest
uv build
```

`uv run tatar-names-audit` prints a JSON summary of the highest-yield cleanup buckets across the source and release data, including preserved generated formations, unresolved exclusions, suspicious repetition patterns, and remaining release collisions.
