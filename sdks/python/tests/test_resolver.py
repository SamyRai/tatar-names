from tatar_names import resolve


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
