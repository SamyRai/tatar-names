import pytest

from tatar_names import normalize
from tatar_names.normalize import Level


def test_safe_normalization_removes_punctuation_and_folds_yo() -> None:
    assert normalize.safe(" Ёлка! ") == "елка"


def test_soft_key_is_candidate_only_and_lossy() -> None:
    assert normalize.soft_key("Иль-мир") == "илмир"


@pytest.mark.parametrize(
    ("name", "canonical", "lookup", "candidate"),
    [
        # Canonical keeps case and ё; lookup lowercases and folds ё→е.
        ("Ёлка", "Ёлка", "елка", "елка"),
        ("ёлка", "ёлка", "елка", "елка"),
        # Lookup keeps the hyphen; candidate drops it together with ь.
        ("Иль-мир", "Иль-мир", "иль-мир", "илмир"),
        # Hyphen class: dash variants all fold to '-' at lookup only.
        ("Ай‐рат", "Ай‐рат", "ай-рат", "аират"),
        ("Ай‑рат", "Ай‑рат", "ай-рат", "аират"),
        ("Ай–рат", "Ай–рат", "ай-рат", "аират"),
        ("Ай—рат", "Ай—рат", "ай-рат", "аират"),
        # Mixed ё/е in one name.
        ("Артём", "Артём", "артем", "артем"),
        # Tatar letters pass through all levels; no ASCII folding here.
        ("Әбелкәрам", "Әбелкәрам", "әбелкәрам", "әбелкәрам"),
        # Canonical composes NFC but does not strip anything.
        ("Е\u0308лка", "Ёлка", "елка", "елка"),
    ],
)
def test_normalization_level_table(
    name: str, canonical: str, lookup: str, candidate: str
) -> None:
    assert normalize.normalize_key(name, Level.CANONICAL) == canonical
    assert normalize.normalize_key(name, Level.LOOKUP) == lookup
    assert normalize.normalize_key(name, Level.CANDIDATE_SEARCH) == candidate


def test_levels_dispatch_to_the_documented_implementations() -> None:
    name = "Иль-мир"
    assert normalize.normalize_key(name, Level.LOOKUP) == normalize.safe(name)
    assert normalize.normalize_key(name, Level.CANDIDATE_SEARCH) == normalize.soft_key(name)
    assert normalize.normalize_key(name, Level.LOOKUP) == normalize.normalize_key(name, "lookup")


def test_canonical_is_not_a_lookup_key() -> None:
    name = " Ёлка! "
    canonical = normalize.normalize_key(name, Level.CANONICAL)
    assert canonical == " Ёлка! "
    assert canonical != normalize.safe(name)


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown normalization level"):
        normalize.normalize_key("Ёлка", "bogus")
