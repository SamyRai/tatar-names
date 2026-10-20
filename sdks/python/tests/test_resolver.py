from __future__ import annotations

from pathlib import Path

from tatar_names import resolve

# Fixture captured verbatim: two identities share the normalized form key
# "айко" (multi-candidate), plus one alias with a near-confusable relation.
IDENTITIES = """name_id,entity_type,gender,canonical_tt_cyrl,canonical_ru_cyrl,canonical_tt_latn,canonical_ru_latn,source_id,source_row,status,notes
ttn_000001,given,male,Айко,Айко,Ayko,Ayko,test,1,canonical,
ttn_000002,given,female,Айко,Айко,Ayko,Ayko,test,2,canonical,
"""

FORMS = """form_id,name_id,form,script,language_tag,form_role,identity_status,profile,confidence,source_id,evidence_id,merge_policy
f_0000001,ttn_000001,Айко,Cyrl,ru-Cyrl,official_ru_or_russified_primary,canonical,ru_adaptation,0.90,test,ev_1,candidate_only
f_0000002,ttn_000002,Айко,Cyrl,ru-Cyrl,official_tt,canonical,tt_original,0.95,test,ev_2,auto_merge
f_0000003,ttn_000001,Aiko,Latn,ru-Latn,passport_latin,variant,ru_cyrl_to_latn_mvd_doc,0.80,test,ev_3,auto_merge
"""

ALIASES = """alias_id,form_id,name_id,alias,script,language_tag,alias_type,method,confidence,merge_policy,source_id,rule_id
a_0000001,f_0000001,ttn_000001,Айчка,Cyrl,ru-Cyrl,common_variant,common_variant,0.85,candidate_only,test,
"""

RELATIONS = """relation_id,left_kind,left_id,right_kind,right_id,relation,merge_policy,confidence,evidence_type,source_id,evidence_id,notes
rel_0000001,name,ttn_000001,name,ttn_000002,near_confusable_but_distinct,never_merge,0.90,manual,test,ev_r1,identical spelling distinct persons
rel_0000002,name,ttn_000002,form,f_0000003,same_name_script_variant,auto_merge,0.95,manual,test,ev_r2,latin variant
"""

ADVISORY = (
    "merge_recommendation describes form-level linkage only; "
    "person-record merges require independent evidence"
)


def _fixture_release(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    release.mkdir()
    (release / "identities.csv").write_text(IDENTITIES, encoding="utf-8")
    (release / "forms.csv").write_text(FORMS, encoding="utf-8")
    (release / "aliases.csv").write_text(ALIASES, encoding="utf-8")
    (release / "relations.csv").write_text(RELATIONS, encoding="utf-8")
    return release


def test_resolves_exact_form() -> None:
    result = resolve.resolve("Эльмир")
    assert result["best_match"]
    assert result["best_match"]["canonical_ru"] == "Эльмир"


def test_guzel_resolves_as_auto_merge_variant() -> None:
    result = resolve.resolve("Guzel")
    assert result["best_match"]
    assert result["best_match"]["canonical_ru"] == "Гузель"
    assert result["best_match"]["merge_policy"] == "auto_merge"
    assert result["best_match"]["match_type"] == "script_variant"


def test_common_variant_does_not_override_exact_canonical() -> None:
    result = resolve.resolve("Ильмир")
    assert result["best_match"]["canonical_ru"] == "Ильмир"


def test_hard_negative_near_misses_are_returned() -> None:
    result = resolve.resolve("Ильмир")
    assert any(item["canonical_ru"] == "Эльмир" for item in result["near_misses"])
    assert any(item["other_canonical_ru"] == "Эльмир" for item in result["relation_warnings"])
    assert result["merge_recommendation"] == "review_required"


def test_auto_merge_form_yields_form_level_recommendation() -> None:
    result = resolve.resolve("Guzel")
    assert result["best_match"]
    assert result["best_match"]["merge_policy"] == "auto_merge"
    assert result["merge_recommendation"] == "form_match_auto_merge"
    assert result["advisory"]
    assert "form-level" in result["advisory"]
    assert "person-record merges require independent evidence" in result["advisory"]


def test_hard_negative_result_still_carries_advisory() -> None:
    result = resolve.resolve("Ильмир")
    assert result["merge_recommendation"] == "review_required"
    assert "person-record merges require independent evidence" in result["advisory"]


def test_unknown_input_yields_no_match_with_advisory() -> None:
    result = resolve.resolve("zzzqqq")
    assert result["best_match"] is None
    assert result["candidates"] == []
    assert result["merge_recommendation"] == "no_match"
    assert "person-record merges require independent evidence" in result["advisory"]


def test_multi_candidate_query_result_is_unchanged(tmp_path: Path) -> None:
    # Expected dict captured from the pre-index implementation; the fixture
    # pins candidate ordering by (confidence, merge_bonus).
    release = _fixture_release(tmp_path)
    result = resolve.resolve("Айко", release)
    assert result == {
        "input": "Айко",
        "best_match": {
            "name_id": "ttn_000002",
            "matched_form": "Айко",
            "matched_form_id": "f_0000002",
            "canonical_ru": "Айко",
            "canonical_tt": "Айко",
            "confidence": 0.95,
            "match_type": "official_form",
            "merge_policy": "auto_merge",
        },
        "candidates": [
            {
                "name_id": "ttn_000002",
                "matched_form": "Айко",
                "matched_form_id": "f_0000002",
                "canonical_ru": "Айко",
                "canonical_tt": "Айко",
                "confidence": 0.95,
                "match_type": "official_form",
                "merge_policy": "auto_merge",
            },
            {
                "name_id": "ttn_000001",
                "matched_form": "Айко",
                "matched_form_id": "f_0000001",
                "canonical_ru": "Айко",
                "canonical_tt": "Айко",
                "confidence": 0.9,
                "match_type": "official_form",
                "merge_policy": "candidate_only",
            },
        ],
        "near_misses": [
            {
                "name_id": "ttn_000001",
                "canonical_ru": "Айко",
                "canonical_tt": "Айко",
                "relation": "near_confusable_but_distinct",
                "confidence": 0.9,
            }
        ],
        "relation_warnings": [
            {
                "relation": "near_confusable_but_distinct",
                "other_name_id": "ttn_000001",
                "other_canonical_ru": "Айко",
                "other_canonical_tt": "Айко",
                "merge_policy": "never_merge",
                "confidence": 0.9,
                "reason": "identical spelling distinct persons",
            }
        ],
        "merge_recommendation": "review_required",
        "advisory": ADVISORY,
    }


def test_alias_fallback_query_result_is_unchanged(tmp_path: Path) -> None:
    # Expected dict captured from the pre-index implementation.
    release = _fixture_release(tmp_path)
    result = resolve.resolve("Айчка", release)
    assert result == {
        "input": "Айчка",
        "best_match": {
            "name_id": "ttn_000001",
            "matched_form": "Айчка",
            "matched_form_id": "f_0000001",
            "canonical_ru": "Айко",
            "canonical_tt": "Айко",
            "confidence": 0.85,
            "match_type": "candidate_only",
            "merge_policy": "candidate_only",
        },
        "candidates": [
            {
                "name_id": "ttn_000001",
                "matched_form": "Айчка",
                "matched_form_id": "f_0000001",
                "canonical_ru": "Айко",
                "canonical_tt": "Айко",
                "confidence": 0.85,
                "match_type": "candidate_only",
                "merge_policy": "candidate_only",
            }
        ],
        "near_misses": [
            {
                "name_id": "ttn_000002",
                "canonical_ru": "Айко",
                "canonical_tt": "Айко",
                "relation": "near_confusable_but_distinct",
                "confidence": 0.9,
            }
        ],
        "relation_warnings": [
            {
                "relation": "near_confusable_but_distinct",
                "other_name_id": "ttn_000002",
                "other_canonical_ru": "Айко",
                "other_canonical_tt": "Айко",
                "merge_policy": "never_merge",
                "confidence": 0.9,
                "reason": "identical spelling distinct persons",
            }
        ],
        "merge_recommendation": "review_required",
        "advisory": ADVISORY,
    }
