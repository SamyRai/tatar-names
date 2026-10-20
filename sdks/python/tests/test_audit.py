from __future__ import annotations

from tatar_names.audit import analyze_patterns


def test_audit_reports_source_and_release_buckets() -> None:
    report = analyze_patterns()

    assert report["totals"]["source_entities"] > 0
    assert report["totals"]["excluded_entities"] > 0
    assert report["totals"]["release_identities"] > 0
    assert report["totals"]["release_relations"] > 0
    assert report["generated_formations"]["stored_in_entities"] == 0
    assert report["generated_formations"]["excluded_patronymics"] > 0
    assert report["source_quality"]["missing_tatar_canonical_excluded"] > 0
    assert report["source_quality"]["cross_type_source_alias_candidates"] == 0
    assert report["release_quality"]["exact_form_collisions"] == 0
    assert report["release_quality"]["alias_redundant_with_canonical"] == 0
    assert report["release_quality"]["names_without_relation_coverage"] == 0


def test_audit_release_quality_shape_is_stable() -> None:
    # Structural guard for the release-quality keys, independent of table
    # contents; perf evidence for the coverage pass lives in the benchmark.
    report = analyze_patterns()

    assert set(report["release_quality"]) == {
        "exact_form_collisions",
        "examples_exact_form_collisions",
        "alias_redundant_with_canonical",
        "alias_by_method",
        "relation_by_type",
        "review_by_reason",
        "names_without_relation_coverage",
        "identities_missing_primary_forms",
        "hard_negative_rules_missing_release_coverage",
        "examples_missing_confusable_rules",
        "examples_redundant_aliases",
    }
    assert isinstance(report["release_quality"]["names_without_relation_coverage"], int)
