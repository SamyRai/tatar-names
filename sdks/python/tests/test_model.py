import pytest

from tatar_names import model


def test_name_entry_from_row() -> None:
    row = {
        "name_id": "ttn_000041",
        "entity_type": "given",
        "gender": "male",
        "canonical_tt_cyrl": "Абак",
        "canonical_ru_cyrl": "Абак",
        "canonical_tt_latn": "Abak",
        "canonical_ru_latn": "Abak",
        "source_id": "zags_2025",
        "source_row": "ev_0000001",
        "status": "active",
        "notes": "",
    }
    entry = model.NameEntry.from_row(row)
    assert entry.name_id == "ttn_000041"
    assert entry.entity_type == "given"
    assert entry.gender == "male"
    assert entry.canonical_tt_cyrl == "Абак"
    assert entry.canonical_ru_latn == "Abak"
    assert entry.status == "active"


def test_name_entry_rejects_bad_name_id() -> None:
    row = {
        "name_id": "tt_41",
        "entity_type": "given",
        "gender": "male",
        "canonical_tt_cyrl": "Абак",
        "canonical_ru_cyrl": "Абак",
        "canonical_tt_latn": "Abak",
        "canonical_ru_latn": "Abak",
        "source_id": "zags_2025",
        "source_row": "ev_0000001",
        "status": "active",
        "notes": "",
    }
    with pytest.raises(ValueError, match=r"name_id: 'tt_41' does not match"):
        model.NameEntry.from_row(row)


def test_name_form_from_row() -> None:
    row = {
        "form_id": "f_0000002",
        "name_id": "ttn_000041",
        "form": "Абак",
        "script": "Cyrl",
        "language_tag": "ru-Cyrl",
        "form_role": "official_ru_or_russified_primary",
        "identity_status": "canonical",
        "profile": "ru_adaptation",
        "confidence": "1.00",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
        "merge_policy": "auto_merge",
    }
    form = model.NameForm.from_row(row)
    assert form.form_id == "f_0000002"
    assert form.name_id == "ttn_000041"
    assert form.form == "Абак"
    assert form.script == "Cyrl"
    assert form.form_role == "official_ru_or_russified_primary"
    assert form.identity_status == "canonical"
    assert form.profile == "ru_adaptation"
    assert form.confidence == "1.00"
    assert form.merge_policy == "auto_merge"


def test_name_form_rejects_bad_merge_policy() -> None:
    row = {
        "form_id": "f_0000002",
        "name_id": "ttn_000041",
        "form": "Абак",
        "script": "Cyrl",
        "language_tag": "ru-Cyrl",
        "form_role": "official_ru_or_russified_primary",
        "identity_status": "canonical",
        "profile": "ru_adaptation",
        "confidence": "1.00",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
        "merge_policy": "merge_it",
    }
    with pytest.raises(ValueError, match=r"merge_policy: 'merge_it' not one of"):
        model.NameForm.from_row(row)


def test_attestation_from_row() -> None:
    row = {
        "attestation_id": "at_0000001",
        "entity_id": "ttn_000041",
        "form": "Абак",
        "script": "Cyrl",
        "language_tag": "ru-Cyrl",
        "form_kind": "canonical",
        "profile": "ru_adaptation",
        "is_canonical": "true",
        "confidence": "1.00",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
    }
    attestation = model.Attestation.from_row(row)
    assert attestation.attestation_id == "at_0000001"
    assert attestation.entity_id == "ttn_000041"
    assert attestation.form == "Абак"
    assert attestation.form_kind == "canonical"
    assert attestation.is_canonical == "true"
    assert attestation.confidence == "1.00"


def test_attestation_rejects_bad_form_kind() -> None:
    row = {
        "attestation_id": "at_0000001",
        "entity_id": "ttn_000041",
        "form": "Абак",
        "script": "Cyrl",
        "language_tag": "ru-Cyrl",
        "form_kind": "invented",
        "profile": "ru_adaptation",
        "is_canonical": "true",
        "confidence": "1.00",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
    }
    with pytest.raises(ValueError, match=r"form_kind: 'invented' not one of"):
        model.Attestation.from_row(row)


def test_relation_assertion_from_row() -> None:
    row = {
        "relation_id": "rel_0000001abcde",
        "left_kind": "name",
        "left_id": "ttn_000041",
        "right_kind": "form",
        "right_id": "f_0000002",
        "relation": "same_name_official_pair",
        "merge_policy": "auto_merge",
        "confidence": "1.00",
        "evidence_type": "source_attestation",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
        "notes": "official_ru_or_russified_primary",
    }
    relation = model.RelationAssertion.from_row(row)
    assert relation.relation_id == "rel_0000001abcde"
    assert relation.left_kind == "name"
    assert relation.left_id == "ttn_000041"
    assert relation.right_kind == "form"
    assert relation.right_id == "f_0000002"
    assert relation.relation == "same_name_official_pair"
    assert relation.confidence == "1.00"


def test_relation_assertion_rejects_bad_relation() -> None:
    row = {
        "relation_id": "rel_0000001abcde",
        "left_kind": "name",
        "left_id": "ttn_000041",
        "right_kind": "form",
        "right_id": "f_0000002",
        "relation": "same_person",
        "merge_policy": "auto_merge",
        "confidence": "1.00",
        "evidence_type": "source_attestation",
        "source_id": "zags_2025",
        "evidence_id": "ev_0000001",
        "notes": "",
    }
    with pytest.raises(ValueError, match=r"relation: 'same_person' not one of"):
        model.RelationAssertion.from_row(row)


def test_review_case_from_row() -> None:
    row = {
        "review_id": "rq_0000001",
        "subject_kind": "form",
        "subject_id": "at_0000001",
        "queue_reason": "superseded_attestation",
        "suggested_relation": "review_candidate",
        "source_id": "tatar_unified_bootstrap",
        "evidence_id": "",
        "notes": "Абак superseded_by=at_0000002",
    }
    case = model.ReviewCase.from_row(row)
    assert case.review_id == "rq_0000001"
    assert case.subject_kind == "form"
    assert case.subject_id == "at_0000001"
    assert case.queue_reason == "superseded_attestation"
    assert case.suggested_relation == "review_candidate"


def test_review_case_allows_empty_suggested_relation() -> None:
    row = {
        "review_id": "rq_0000002",
        "subject_kind": "rule",
        "subject_id": "double_letter",
        "queue_reason": "rule_tuning",
        "suggested_relation": "",
        "source_id": "tatar_unified_bootstrap",
        "evidence_id": "",
        "notes": "",
    }
    case = model.ReviewCase.from_row(row)
    assert case.suggested_relation == ""


def test_review_case_rejects_bad_subject_kind() -> None:
    row = {
        "review_id": "rq_0000001",
        "subject_kind": "person",
        "subject_id": "at_0000001",
        "queue_reason": "superseded_attestation",
        "suggested_relation": "",
        "source_id": "tatar_unified_bootstrap",
        "evidence_id": "",
        "notes": "",
    }
    with pytest.raises(ValueError, match=r"subject_kind: 'person' not one of"):
        model.ReviewCase.from_row(row)
