import pytest

from tatar_names import transliterate
from tatar_names.transliterate import PROFILE_FILES, profiles


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


def test_transliterate_outputs_unchanged_by_profile_string() -> None:
    assert transliterate.transliterate("Мөхәммәт", "tt_cyrl_to_tt_latn_rt2013") == "Moxammat"
    assert transliterate.transliterate("Мухаммет", "ru_cyrl_to_latn_mvd_doc") == "Mukhammet"


def test_profile_contracts_are_pinned() -> None:
    contracts = {contract.profile_id: contract for contract in profiles()}
    assert set(contracts) == {
        "tt_cyrl_to_tt_latn_rt2013",
        "ru_cyrl_to_latn_mvd_doc",
    }
    tt = contracts["tt_cyrl_to_tt_latn_rt2013"]
    assert tt.purpose == "search_candidate"
    assert tt.lossy is True
    assert tt.legal_authority is False
    ru = contracts["ru_cyrl_to_latn_mvd_doc"]
    assert ru.purpose == "documentary_candidate"
    assert ru.lossy is True
    assert ru.legal_authority is False


def test_available_profiles_matches_contract_ids() -> None:
    assert transliterate.available_profiles() == tuple(
        contract.profile_id for contract in profiles()
    )
    assert set(transliterate.available_profiles()) == set(PROFILE_FILES)


def test_unknown_profile_error_message() -> None:
    with pytest.raises(ValueError, match=r"^Unknown transliteration profile: nope$"):
        transliterate.transliterate("Мөхәммәт", "nope")
