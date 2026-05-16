from tatar_names.audit import analyze_patterns


def test_audit_reports_source_and_release_buckets() -> None:
    report = analyze_patterns()

    assert report["totals"]["source_entities"] > 0
    assert report["totals"]["excluded_entities"] > 0
    assert report["generated_formations"]["stored_in_entities"] == 0
    assert report["generated_formations"]["excluded_patronymics"] > 0
    assert report["source_quality"]["missing_tatar_canonical_excluded"] > 0
    assert report["release_quality"]["exact_form_collisions"] == 0
