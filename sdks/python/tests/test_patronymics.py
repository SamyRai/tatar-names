from tatar_names.formations import generate_patronymic
from tatar_names.transliterate import ru_to_latin


def patronymic_base(ru_cyrl: str, ru_latn: str) -> dict[str, str]:
    return {
        "canonical_tt_cyrl": ru_cyrl,
        "canonical_ru_cyrl": ru_cyrl,
        "canonical_tt_latn": ru_latn,
        "canonical_ru_latn": ru_latn,
    }


def test_generate_patronymic_keeps_soft_stem_for_yi_bases() -> None:
    male = generate_patronymic(patronymic_base("Юрий", "Yuriy"), "male")
    female = generate_patronymic(patronymic_base("Юрий", "Yuriy"), "female")
    assert male["canonical_ru_cyrl"] == "Юрьевич"
    assert female["canonical_ru_cyrl"] == "Юрьевна"


def test_generate_patronymic_strips_soft_sign_base() -> None:
    male = generate_patronymic(patronymic_base("Игорь", "Igor"), "male")
    female = generate_patronymic(patronymic_base("Игорь", "Igor"), "female")
    assert male["canonical_ru_cyrl"] == "Игоревич"
    assert male["canonical_ru_latn"] == "Igorevich"
    assert female["canonical_ru_cyrl"] == "Игоревна"
    assert female["canonical_ru_latn"] == "Igorevna"


def test_generate_patronymic_plain_yi_base_takes_evich_evna() -> None:
    male = generate_patronymic(patronymic_base("Абдельхай", "Abdelkhai"), "male")
    female = generate_patronymic(patronymic_base("Абдельхай", "Abdelkhai"), "female")
    assert male["canonical_ru_cyrl"] == "Абдельхаевич"
    assert female["canonical_ru_cyrl"] == "Абдельхаевна"
    assert female["canonical_ru_latn"] == "Abdelkhaievna"


def test_generate_patronymic_latin_stem_matches_cyrillic_for_yi_bases() -> None:
    # "Iurii" is this repo's own map transliteration of Юрий (ю→iu, и→i, й→i).
    # The Cyrillic stem keeps a soft sign (Юрь-), which the Latin map drops, so
    # the Latin stem is "Iur" and the suffixes are parallel: ьевич ↔ evich.
    result = generate_patronymic(patronymic_base("Юрий", "Iurii"), "male")
    assert result["canonical_ru_cyrl"] == "Юрьевич"
    assert result["canonical_ru_latn"] == "Iurevich"
    assert result["canonical_ru_latn"] == ru_to_latin(result["canonical_ru_cyrl"])


def test_generate_patronymic_latin_stem_matches_cyrillic_for_soft_sign_bases() -> None:
    # ь has no Latin transliteration, so the Latin stem equals the Cyrillic stem
    # transliterated: Игор- ↔ Igor, Игоревич ↔ Igorevich.
    result = generate_patronymic(patronymic_base("Игорь", "Igor"), "male")
    assert result["canonical_ru_latn"] == ru_to_latin(result["canonical_ru_cyrl"])
