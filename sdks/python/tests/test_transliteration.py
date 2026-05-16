from tatar_names import transliterate


def test_ru_to_latin() -> None:
    assert transliterate.ru_to_latin("Мухаммет") == "Mukhammet"


def test_tt_to_latin_handles_tatar_letters() -> None:
    assert transliterate.tt_to_latin("Мөхәммәт") == "Moxammat"
