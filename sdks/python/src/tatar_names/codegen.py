"""Dev-time code generator: the JSON Schema files are the single source of truth.

Reads the live JSON Schema 2020-12 files from schemas/ and emits:

- Frictionless Table Schema JSON per tabular release resource into
  ``schemas/tableschema/<table>.tableschema.json`` (identities, forms,
  relations, review_queue, aliases).
- ``sdks/python/src/tatar_names/_contracts.py`` with the VALID_* validation
  sets used by ``pipeline.py``.

Scoping decisions recorded here so the generator stays self-describing:

- ``names.schema.json`` is legacy (its table was removed from the release) and
  is excluded from the live inventory.
- ``entities``, ``attestations`` and ``excluded_entities`` are source tables,
  not tabular release resources, so they get no Table Schema; they still
  contribute enum values to ``_contracts.py``.
- ``review_queue`` has no foreign key: ``subject_id`` is polymorphic and
  ``subject_kind`` selects the referenced table. ``relations`` likewise has no
  foreign key: ``left_id``/``right_id`` are polymorphic via the kind columns.
- Table Schema constraints use the XSD regular-expression dialect, so JSON
  Schema patterns are translated (``\\d`` -> ``[0-9]``) before emission.

Usage::

    python -m tatar_names.codegen           regenerate all outputs
    python -m tatar_names.codegen --check   verify committed outputs are fresh
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .data import project_root

SCHEMAS_DIR = "schemas"
TABLE_SCHEMA_SUBDIR = "tableschema"
CONTRACTS_RELPATH = "sdks/python/src/tatar_names/_contracts.py"

#: Exact live inventory; must be extended explicitly when a schema is added.
LIVE_SCHEMA_STEMS: tuple[str, ...] = (
    "aliases",
    "attestations",
    "entities",
    "excluded_entities",
    "forms",
    "identities",
    "relations",
    "review_queue",
)

#: Known-legacy schemas kept in schemas/ but excluded from codegen.
LEGACY_SCHEMA_STEMS: tuple[str, ...] = ("names",)

#: Release tables that are tabular resources and therefore get a Table Schema.
RELEASE_TABLES: dict[str, str] = {
    "identities": "identities.schema.json",
    "forms": "forms.schema.json",
    "relations": "relations.schema.json",
    "review_queue": "review_queue.schema.json",
    "aliases": "aliases.schema.json",
}

PRIMARY_KEYS: dict[str, str] = {
    "identities": "name_id",
    "forms": "form_id",
    "relations": "relation_id",
    "review_queue": "review_id",
    "aliases": "alias_id",
}

#: Only unambiguous foreign keys; polymorphic subjects stay key-less.
FOREIGN_KEYS: dict[str, list[dict[str, Any]]] = {
    "forms": [
        {"fields": ["name_id"], "reference": {"resource": "identities", "fields": ["name_id"]}},
    ],
    "aliases": [
        {"fields": ["form_id"], "reference": {"resource": "forms", "fields": ["form_id"]}},
        {"fields": ["name_id"], "reference": {"resource": "identities", "fields": ["name_id"]}},
    ],
}

#: constant name -> (schema stem, owning property).
CONTRACT_CONSTANTS: tuple[tuple[str, str, str], ...] = (
    ("VALID_ENTITY_TYPES", "entities", "entity_type"),
    ("VALID_GENDERS", "entities", "gender"),
    ("VALID_STATUSES", "entities", "status"),
    ("VALID_SCRIPTS", "forms", "script"),
    ("VALID_FORM_KINDS", "attestations", "form_kind"),
    ("VALID_FORM_PROFILES", "attestations", "profile"),
    ("VALID_FORM_ROLES", "forms", "form_role"),
    ("VALID_IDENTITY_STATUSES", "forms", "identity_status"),
    ("VALID_MERGE_POLICIES", "forms", "merge_policy"),
    ("VALID_RELATIONS", "relations", "relation"),
    ("VALID_LINK_KINDS", "relations", "left_kind"),
    ("VALID_REVIEW_SUBJECT_KINDS", "review_queue", "subject_kind"),
)

_GENERATED_HEADER = (
    "# GENERATED FILE - do not edit by hand.\n"
    "# Regenerate with: python -m tatar_names.codegen\n"
    "# Source of truth: schemas/*.schema.json (JSON Schema 2020-12).\n"
)

_JSON_DIALECT_SHORTCUTS = {
    "d": "[0-9]",
    "D": "[^0-9]",
    "w": "[A-Za-z0-9_]",
    "W": "[^A-Za-z0-9_]",
    "s": r" \t\n\r\f\v",
    "S": r"[^ \t\n\r\f\v]",
}


def to_xsd_pattern(pattern: str) -> str:
    """Translate a JSON Schema (ECMA) regex into the XSD-safe dialect.

    Character-class shortcuts such as ``\\d`` are expanded so downstream Table
    Schema validators only need XSD escapes. Escaped literals pass through
    untouched, and ``\\d`` inside a character class drops its brackets.
    """
    out: list[str] = []
    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            replacement = _JSON_DIALECT_SHORTCUTS.get(nxt)
            if replacement is not None:
                out.append(replacement.strip("[]") if in_class else replacement)
            else:
                out.append(pattern[i : i + 2])
            i += 2
            continue
        if char == "[" and not in_class:
            in_class = True
        elif char == "]" and in_class:
            in_class = False
        out.append(char)
        i += 1
    return "".join(out)


def load_inventory(root: Path) -> dict[str, dict[str, Any]]:
    """Load the live JSON Schema files, keyed by file stem.

    Raises when the on-disk inventory drifts from the recorded list, so a new
    schema file forces an explicit generator update.
    """
    schemas_dir = root / SCHEMAS_DIR
    found = {path.name.removesuffix(".schema.json") for path in schemas_dir.glob("*.schema.json")}
    unknown = found - set(LIVE_SCHEMA_STEMS) - set(LEGACY_SCHEMA_STEMS)
    missing = set(LIVE_SCHEMA_STEMS) - found
    if unknown or missing:
        raise ValueError(
            "schema inventory changed: "
            f"unknown={sorted(unknown)} missing={sorted(missing)}; "
            "update codegen.LIVE_SCHEMA_STEMS"
        )
    inventory: dict[str, dict[str, Any]] = {}
    for stem in LIVE_SCHEMA_STEMS:
        path = schemas_dir / f"{stem}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        if schema.get("type") != "object" or "properties" not in schema:
            raise ValueError(f"{path.name}: expected an object schema with properties")
        inventory[stem] = schema
    return inventory


def _field_constraints(prop: Mapping[str, Any], *, required: bool) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    if required:
        constraints["required"] = True
    if "enum" in prop:
        constraints["enum"] = list(prop["enum"])
    if "pattern" in prop:
        constraints["pattern"] = to_xsd_pattern(prop["pattern"])
    if "minLength" in prop:
        constraints["minLength"] = prop["minLength"]
    if "maxLength" in prop:
        constraints["maxLength"] = prop["maxLength"]
    return constraints


def build_table_schema(table: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    required = set(schema.get("required", []))
    fields: list[dict[str, Any]] = []
    for name, prop in schema["properties"].items():
        if prop.get("type") != "string":
            raise ValueError(f"{table}.{name}: only string fields are supported")
        constraints = _field_constraints(prop, required=name in required)
        field: dict[str, Any] = {"name": name, "type": "string"}
        if constraints:
            field["constraints"] = constraints
        fields.append(field)
    descriptor: dict[str, Any] = {"fields": fields, "primaryKey": [PRIMARY_KEYS[table]]}
    foreign_keys = FOREIGN_KEYS.get(table)
    if foreign_keys:
        descriptor["foreignKeys"] = foreign_keys
    return descriptor


def _format_set_literal(values: Sequence[str], indent: str) -> str:
    if not values:
        return "set()"
    single_line = "{" + ", ".join(json.dumps(value) for value in values) + "}"
    if len(indent + single_line) <= 88:
        return single_line
    lines = [indent + "{"]
    lines.extend(f"{indent}    {json.dumps(value)}," for value in values)
    lines.append(indent + "}")
    return "\n".join(lines)


def render_contracts(inventory: Mapping[str, Mapping[str, Any]]) -> str:
    lines = [
        _GENERATED_HEADER,
        "from __future__ import annotations",
        "",
    ]
    for constant, stem, prop_name in CONTRACT_CONSTANTS:
        prop = inventory[stem]["properties"][prop_name]
        if "enum" not in prop:
            raise ValueError(f"{stem}.schema.json property {prop_name} has no enum")
        values = sorted(prop["enum"])
        lines.append(f"{constant} = {_format_set_literal(values, indent='')}")
    return "\n".join(lines) + "\n"


def build_outputs(inventory: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Render every generated file as relpath -> text content."""
    outputs: dict[str, str] = {}
    for table, schema_file in RELEASE_TABLES.items():
        stem = schema_file.removesuffix(".schema.json")
        descriptor = build_table_schema(table, inventory[stem])
        relpath = f"{SCHEMAS_DIR}/{TABLE_SCHEMA_SUBDIR}/{table}.tableschema.json"
        outputs[relpath] = json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n"
    outputs[CONTRACTS_RELPATH] = render_contracts(inventory)
    return outputs


def detect_drift(root: Path, expected: Mapping[str, str]) -> list[str]:
    """Compare expected content against committed files; returns drift labels."""
    drifts: list[str] = []
    for relpath in sorted(expected):
        target = root / relpath
        if not target.exists():
            drifts.append(f"missing: {relpath}")
        elif target.read_text(encoding="utf-8") != expected[relpath]:
            drifts.append(f"out of date: {relpath}")
    table_schema_dir = root / SCHEMAS_DIR / TABLE_SCHEMA_SUBDIR
    if table_schema_dir.is_dir():
        expected_names = {
            Path(relpath).name
            for relpath in expected
            if relpath.startswith(f"{SCHEMAS_DIR}/{TABLE_SCHEMA_SUBDIR}/")
        }
        for path in sorted(table_schema_dir.glob("*.tableschema.json")):
            if path.name not in expected_names:
                drifts.append(f"unexpected: {SCHEMAS_DIR}/{TABLE_SCHEMA_SUBDIR}/{path.name}")
    return drifts


def _diff_summary(root: Path, expected: Mapping[str, str]) -> list[str]:
    lines: list[str] = []
    for relpath in sorted(expected):
        target = root / relpath
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        diff = list(
            difflib.unified_diff(
                current.splitlines(),
                expected[relpath].splitlines(),
                fromfile=relpath,
                tofile=f"{relpath} (generated)",
                lineterm="",
            )
        )
        if diff:
            lines.extend(diff[:40])
            if len(diff) > 40:
                lines.append(f"  ... {len(diff) - 40} more diff lines")
    return lines


def write_outputs(root: Path, expected: Mapping[str, str]) -> list[str]:
    written: list[str] = []
    for relpath in sorted(expected):
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected[relpath], encoding="utf-8")
        written.append(relpath)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tatar_names.codegen",
        description="Generate Table Schemas and validation contracts from schemas/*.schema.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and exit 1 if committed outputs drift",
    )
    args = parser.parse_args(argv)

    root = project_root()
    expected = build_outputs(load_inventory(root))
    if args.check:
        drifts = detect_drift(root, expected)
        if drifts:
            print("generated outputs are out of date:")
            for drift in drifts:
                print(f"  {drift}")
            for line in _diff_summary(root, expected):
                print(line)
            print("run: python -m tatar_names.codegen")
            return 1
        print("generated outputs are up to date")
        return 0
    for relpath in write_outputs(root, expected):
        print(f"wrote {relpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
