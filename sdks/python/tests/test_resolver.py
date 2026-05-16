from tatar_names import resolve


def test_resolves_exact_form() -> None:
    result = resolve.resolve("Эльмир")
    assert result["best_match"]
    assert result["best_match"]["canonical_ru"] == "Эльмир"


def test_result_has_no_relation_warnings_field() -> None:
    result = resolve.resolve("Эльмир")
    assert "do_not_merge_warnings" not in result


def test_common_variant_does_not_override_exact_canonical() -> None:
    result = resolve.resolve("Ильмир")
    assert result["best_match"]["canonical_ru"] == "Ильмир"
