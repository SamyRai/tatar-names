from tatar_names import transliterate


def test_ru_to_latin() -> None:
    assert transliterate.ru_to_latin("Мухаммет") == "Mukhammet"


def test_tt_to_latin_handles_tatar_letters() -> None:
    assert transliterate.tt_to_latin("Мөхәммәт") == "Moxammat"


def test_ru_to_latin_uppercase_run_uses_uppercase_multiletter_maps() -> None:
    # ЦАРЕВ: ц→ts, а→a, р→r, е→e, в→v. Inside an all-caps run every mapping
    # is rendered uppercase, so multi-letter maps do not degrade to TsAR-style mixes.
    assert transliterate.ru_to_latin("ЦАРЕВ") == "TSAREV"
    assert transliterate.ru_to_latin("ХАН") == "KHAN"


def test_ru_to_latin_uppercase_run_ends_capitalized() -> None:
    # ЦАРЬ: ц→ts (followed by uppercase), а→a, р→r caps the run's end, ь→"".
    assert transliterate.ru_to_latin("ЦАРЬ") == "TSAR"


def test_ru_to_latin_mixed_case_unchanged() -> None:
    assert transliterate.ru_to_latin("Царев") == "Tsarev"


def test_ru_to_latin_transliterates_hard_sign_as_ie() -> None:
    # Подъячев letter by letter: п→p, о→o, д→d, ъ→ie, я→ia, ч→ch, е→e, в→v.
    assert transliterate.ru_to_latin("Подъячев") == "Podieiachev"
