from tatar_names import normalize


def test_safe_normalization_removes_punctuation_and_folds_yo() -> None:
    assert normalize.safe(" Ёлка! ") == "елка"


def test_soft_key_is_candidate_only_and_lossy() -> None:
    assert normalize.soft_key("Иль-мир") == "илмир"
