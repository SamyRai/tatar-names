from tatar_names.formations import detect_generated_formation, generate_patronymic


def test_generate_patronymic_uses_ovich_for_default_ru_base() -> None:
    result = generate_patronymic(
        {
            "canonical_tt_cyrl": "Әбелкәрам",
            "canonical_ru_cyrl": "Абелькарам",
            "canonical_tt_latn": "Abelkaram",
            "canonical_ru_latn": "Abelkaram",
        },
        "male",
    )
    assert result["canonical_tt_cyrl"] == "Әбелкәрам улы"
    assert result["canonical_ru_cyrl"] == "Абелькарамович"


def test_generate_patronymic_uses_evich_for_soft_ru_ending() -> None:
    result = generate_patronymic(
        {
            "canonical_tt_cyrl": "Әбделхәй",
            "canonical_ru_cyrl": "Абдельхай",
            "canonical_tt_latn": "Abdelxay",
            "canonical_ru_latn": "Abdelkhai",
        },
        "male",
    )
    assert result["canonical_ru_cyrl"] == "Абдельхаевич"
    assert result["canonical_ru_latn"] == "Abdelkhaievich"


def test_detect_generated_formation_flags_repeated_suffixes() -> None:
    match = detect_generated_formation(
        {
            "canonical_tt_cyrl": "Вәлияр улы улы",
            "canonical_ru_cyrl": "Валиярович",
            "canonical_tt_latn": "Valiyar uly uly",
            "canonical_ru_latn": "Valiyarovich",
            "gender": "male",
        }
    )
    assert match
    assert match.classification == "malformed_generated"
