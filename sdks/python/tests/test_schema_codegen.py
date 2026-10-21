from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tatar_names import _contracts, codegen, pipeline

ROOT = Path(__file__).resolve().parents[3]

CONFIDENCE_XSD_PATTERN = "^(0(\\.[0-9]+)?|1(\\.0+)?)$"


@pytest.fixture(scope="module")
def inventory() -> dict:
    return codegen.load_inventory(ROOT)


@pytest.fixture(scope="module")
def outputs(inventory: dict) -> dict[str, str]:
    return codegen.build_outputs(inventory)


def _table_schema(outputs: dict[str, str], table: str) -> dict:
    return json.loads(outputs[f"schemas/tableschema/{table}.tableschema.json"])


def test_live_inventory_excludes_legacy_schema(inventory: dict) -> None:
    assert sorted(inventory) == sorted(codegen.LIVE_SCHEMA_STEMS)
    assert "names" not in inventory


def test_identities_table_schema_fields_and_constraints(outputs: dict[str, str]) -> None:
    doc = _table_schema(outputs, "identities")
    expected_constraints = {
        "name_id": {"required": True, "pattern": "^ttn_[0-9]{6}$"},
        "entity_type": {"required": True, "enum": ["given", "surname"]},
        "gender": {"required": True, "enum": ["male", "female", "unisex", "unknown"]},
        "origin_family": {"required": True, "minLength": 1},
        "usage_community": {"required": True, "minLength": 1},
        "canonical_tt_cyrl": {"required": True, "minLength": 1},
        "canonical_ru_cyrl": {"required": True, "minLength": 1},
        "canonical_tt_latn": {"required": True, "minLength": 1},
        "canonical_ru_latn": {"required": True, "minLength": 1},
        "primary_form_global": {"required": True, "minLength": 1},
        "primary_form_tt": {"required": True, "minLength": 1},
        "primary_form_ru": {"required": True, "minLength": 1},
        "source_id": {"required": True, "minLength": 1},
        "source_row": {"required": True},
        "status": {"required": True, "enum": ["active", "deprecated", "disputed"]},
        "notes": {"required": True},
    }
    assert [field["name"] for field in doc["fields"]] == list(expected_constraints)
    assert all(field["type"] == "string" for field in doc["fields"])
    assert {field["name"]: field["constraints"] for field in doc["fields"]} == expected_constraints
    assert doc["primaryKey"] == ["name_id"]
    assert "foreignKeys" not in doc


def test_forms_table_schema_fields_and_constraints(outputs: dict[str, str]) -> None:
    doc = _table_schema(outputs, "forms")
    expected_constraints = {
        "form_id": {"required": True, "pattern": "^f_[0-9]{7}$"},
        "name_id": {"required": True, "pattern": "^ttn_[0-9]{6}$"},
        "form": {"required": True, "minLength": 1},
        "script": {"required": True, "enum": ["Cyrl", "Latn"]},
        "language_tag": {"required": True, "minLength": 1},
        "form_role": {
            "required": True,
            "enum": [
                "official_tt",
                "official_ru_or_russified_primary",
                "tt_latin_transliteration",
                "passport_latin",
                "common_observed",
            ],
        },
        "identity_status": {"required": True, "enum": ["canonical", "variant", "alias", "ambiguous_candidate"]},
        "profile": {
            "required": True,
            "enum": [
                "ru_adaptation",
                "tt_original",
                "tt_cyrl_to_tt_latn_rt2013",
                "ru_cyrl_to_latn_mvd_doc",
                "common_variant",
            ],
        },
        "confidence": {"required": True, "pattern": CONFIDENCE_XSD_PATTERN},
        "source_id": {"required": True, "minLength": 1},
        "evidence_id": {"required": True},
        "merge_policy": {
            "required": True,
            "enum": ["auto_merge", "candidate_only", "never_merge", "review_required"],
        },
    }
    assert [field["name"] for field in doc["fields"]] == list(expected_constraints)
    assert {field["name"]: field["constraints"] for field in doc["fields"]} == expected_constraints
    assert doc["primaryKey"] == ["form_id"]
    assert doc["foreignKeys"] == [
        {"fields": ["name_id"], "reference": {"resource": "identities", "fields": ["name_id"]}},
    ]


def test_aliases_table_schema_has_both_foreign_keys(outputs: dict[str, str]) -> None:
    doc = _table_schema(outputs, "aliases")
    assert doc["primaryKey"] == ["alias_id"]
    assert doc["foreignKeys"] == [
        {"fields": ["form_id"], "reference": {"resource": "forms", "fields": ["form_id"]}},
        {"fields": ["name_id"], "reference": {"resource": "identities", "fields": ["name_id"]}},
    ]


def test_review_queue_has_no_foreign_keys(outputs: dict[str, str]) -> None:
    doc = _table_schema(outputs, "review_queue")
    assert doc["primaryKey"] == ["review_id"]
    assert "foreignKeys" not in doc


def test_relations_table_schema_primary_key(outputs: dict[str, str]) -> None:
    doc = _table_schema(outputs, "relations")
    assert doc["primaryKey"] == ["relation_id"]
    assert "foreignKeys" not in doc


def test_contracts_sets_match_owning_schema_enums(inventory: dict) -> None:
    for constant, stem, prop_name in codegen.CONTRACT_CONSTANTS:
        expected = set(inventory[stem]["properties"][prop_name]["enum"])
        assert getattr(_contracts, constant) == expected, constant


def test_pipeline_constants_are_the_generated_objects() -> None:
    for constant, _stem, _prop in codegen.CONTRACT_CONSTANTS:
        assert hasattr(pipeline, constant), constant
        assert getattr(pipeline, constant) is getattr(_contracts, constant), constant


@pytest.mark.parametrize(
    ("json_pattern", "xsd_pattern"),
    [
        (r"\d", "[0-9]"),
        (r"\D", "[^0-9]"),
        (r"\w", "[A-Za-z0-9_]"),
        (r"[\d_]+", "[0-9_]+"),
        (r"^(0(\.\d+)?|1(\.0+)?)$", CONFIDENCE_XSD_PATTERN),
        ("^ttn_[0-9]{6}$", "^ttn_[0-9]{6}$"),
        (r"a\.b", r"a\.b"),
    ],
)
def test_to_xsd_pattern_translates_json_dialect(json_pattern: str, xsd_pattern: str) -> None:
    assert codegen.to_xsd_pattern(json_pattern) == xsd_pattern


def test_drift_detection_catches_mutated_enum(inventory: dict) -> None:
    mutated = copy.deepcopy(inventory)
    mutated["forms"]["properties"]["script"]["enum"] = ["Cyrl", "Latn", "Arab"]
    mutated_outputs = codegen.build_outputs(mutated)
    drifts = codegen.detect_drift(ROOT, mutated_outputs)
    assert any("out of date: sdks/python/src/tatar_names/_contracts.py" in drift for drift in drifts)
    assert any("out of date: schemas/tableschema/forms.tableschema.json" in drift for drift in drifts)
    assert codegen.detect_drift(ROOT, codegen.build_outputs(inventory)) == []


def test_committed_outputs_are_fresh() -> None:
    expected = codegen.build_outputs(codegen.load_inventory(ROOT))
    assert codegen.detect_drift(ROOT, expected) == []
