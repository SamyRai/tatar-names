"""Explicit domain vocabulary for the dataset's five core concepts.

Raw CSV/JSON rows conflate lexical identity, observed forms, source
attestations, asserted relations and queued review items into dicts. The
classes here give each concept a typed, frozen shape and validate, at
construction, the invariants the JSON Schemas already pin.

The closed vocabularies below mirror schemas/*.schema.json; schema codegen is
the authority and these restatements must be kept in sync with it. They are
deliberately restated locally (rather than imported) so this module depends on
nothing but the published schema contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

NAME_ID_RE = re.compile(r"^ttn_[0-9]{6}$")
FORM_ID_RE = re.compile(r"^f_[0-9]{7}$")
ATTESTATION_ID_RE = re.compile(r"^at_[0-9]{7}$")
RELATION_ID_RE = re.compile(r"^rel_[0-9a-f]{12}$")
REVIEW_ID_RE = re.compile(r"^rq_[0-9]{7}$")
CONFIDENCE_RE = re.compile(r"^(0(\.\d+)?|1(\.0+)?)$")

GENDERS = frozenset({"male", "female", "unisex", "unknown"})
ENTITY_TYPES = frozenset({"given", "surname"})
STATUSES = frozenset({"active", "deprecated", "disputed"})
SCRIPTS = frozenset({"Cyrl", "Latn"})
FORM_KINDS = frozenset({"canonical", "observed_variant", "transliterated", "normalized_source"})
FORM_PROFILES = frozenset(
    {
        "ru_adaptation",
        "tt_original",
        "tt_cyrl_to_tt_latn_rt2013",
        "ru_cyrl_to_latn_mvd_doc",
        "common_variant",
    }
)
FORM_ROLES = frozenset(
    {
        "official_tt",
        "official_ru_or_russified_primary",
        "tt_latin_transliteration",
        "passport_latin",
        "common_observed",
    }
)
IDENTITY_STATUSES = frozenset({"canonical", "variant", "alias"})
MERGE_POLICIES = frozenset({"auto_merge", "candidate_only", "never_merge", "review_required"})
RELATIONS = frozenset(
    {
        "same_name_official_pair",
        "same_name_script_variant",
        "same_name_adapted_form",
        "same_etymon_but_distinct",
        "possible_variant",
        "near_confusable_but_distinct",
        "russified_primary_form",
        "tatarized_form_of_non_tatar_name",
        "review_candidate",
    }
)
LINK_KINDS = frozenset({"name", "form"})
REVIEW_SUBJECT_KINDS = frozenset({"excluded_entity", "form", "relation", "rule"})


def _field(row: Mapping[str, str], name: str) -> str:
    try:
        return row[name]
    except KeyError:
        raise ValueError(f"missing required field {name!r}") from None


def _matches(field: str, value: str, pattern: re.Pattern[str]) -> None:
    if not pattern.fullmatch(value):
        raise ValueError(f"{field}: {value!r} does not match {pattern.pattern!r}")


def _one_of(field: str, value: str, allowed: frozenset[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{field}: {value!r} not one of {sorted(allowed)}")


def _nonempty(field: str, value: str) -> None:
    if not value:
        raise ValueError(f"{field} must be non-empty")


@dataclass(frozen=True)
class NameEntry:
    """One lexical entry: the canonical identity of a name, not a person."""

    name_id: str
    entity_type: str
    gender: str
    canonical_tt_cyrl: str
    canonical_ru_cyrl: str
    canonical_tt_latn: str
    canonical_ru_latn: str
    source_id: str
    source_row: str
    status: str
    notes: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> NameEntry:
        _matches("name_id", _field(row, "name_id"), NAME_ID_RE)
        _one_of("entity_type", _field(row, "entity_type"), ENTITY_TYPES)
        _one_of("gender", _field(row, "gender"), GENDERS)
        _nonempty("canonical_ru_cyrl", _field(row, "canonical_ru_cyrl"))
        _nonempty("source_id", _field(row, "source_id"))
        _one_of("status", _field(row, "status"), STATUSES)
        return cls(
            name_id=row["name_id"],
            entity_type=row["entity_type"],
            gender=row["gender"],
            canonical_tt_cyrl=row["canonical_tt_cyrl"],
            canonical_ru_cyrl=row["canonical_ru_cyrl"],
            canonical_tt_latn=row["canonical_tt_latn"],
            canonical_ru_latn=row["canonical_ru_latn"],
            source_id=row["source_id"],
            source_row=row["source_row"],
            status=row["status"],
            notes=row["notes"],
        )


@dataclass(frozen=True)
class NameForm:
    """One observed or generated concrete spelling of a NameEntry."""

    form_id: str
    name_id: str
    form: str
    script: str
    language_tag: str
    form_role: str
    identity_status: str
    profile: str
    confidence: str
    source_id: str
    evidence_id: str
    merge_policy: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> NameForm:
        _matches("form_id", _field(row, "form_id"), FORM_ID_RE)
        _matches("name_id", _field(row, "name_id"), NAME_ID_RE)
        _nonempty("form", _field(row, "form"))
        _one_of("script", _field(row, "script"), SCRIPTS)
        _nonempty("language_tag", _field(row, "language_tag"))
        _one_of("form_role", _field(row, "form_role"), FORM_ROLES)
        _one_of("identity_status", _field(row, "identity_status"), IDENTITY_STATUSES)
        _one_of("profile", _field(row, "profile"), FORM_PROFILES)
        _matches("confidence", _field(row, "confidence"), CONFIDENCE_RE)
        _nonempty("source_id", _field(row, "source_id"))
        _one_of("merge_policy", _field(row, "merge_policy"), MERGE_POLICIES)
        return cls(
            form_id=row["form_id"],
            name_id=row["name_id"],
            form=row["form"],
            script=row["script"],
            language_tag=row["language_tag"],
            form_role=row["form_role"],
            identity_status=row["identity_status"],
            profile=row["profile"],
            confidence=row["confidence"],
            source_id=row["source_id"],
            evidence_id=row["evidence_id"],
            merge_policy=row["merge_policy"],
        )


@dataclass(frozen=True)
class Attestation:
    """One source-backed observation underlying a NameForm."""

    attestation_id: str
    entity_id: str
    form: str
    script: str
    language_tag: str
    form_kind: str
    profile: str
    is_canonical: str
    confidence: str
    source_id: str
    evidence_id: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> Attestation:
        _matches("attestation_id", _field(row, "attestation_id"), ATTESTATION_ID_RE)
        _matches("entity_id", _field(row, "entity_id"), NAME_ID_RE)
        _nonempty("form", _field(row, "form"))
        _one_of("script", _field(row, "script"), SCRIPTS)
        _nonempty("language_tag", _field(row, "language_tag"))
        _one_of("form_kind", _field(row, "form_kind"), FORM_KINDS)
        _one_of("profile", _field(row, "profile"), FORM_PROFILES)
        _one_of("is_canonical", _field(row, "is_canonical"), frozenset({"true", "false"}))
        _matches("confidence", _field(row, "confidence"), CONFIDENCE_RE)
        _nonempty("source_id", _field(row, "source_id"))
        return cls(
            attestation_id=row["attestation_id"],
            entity_id=row["entity_id"],
            form=row["form"],
            script=row["script"],
            language_tag=row["language_tag"],
            form_kind=row["form_kind"],
            profile=row["profile"],
            is_canonical=row["is_canonical"],
            confidence=row["confidence"],
            source_id=row["source_id"],
            evidence_id=row["evidence_id"],
        )


@dataclass(frozen=True)
class RelationAssertion:
    """One typed edge assertion between two dataset objects."""

    relation_id: str
    left_kind: str
    left_id: str
    right_kind: str
    right_id: str
    relation: str
    merge_policy: str
    confidence: str
    evidence_type: str
    source_id: str
    evidence_id: str
    notes: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> RelationAssertion:
        _matches("relation_id", _field(row, "relation_id"), RELATION_ID_RE)
        _one_of("left_kind", _field(row, "left_kind"), LINK_KINDS)
        _nonempty("left_id", _field(row, "left_id"))
        _one_of("right_kind", _field(row, "right_kind"), LINK_KINDS)
        _nonempty("right_id", _field(row, "right_id"))
        _one_of("relation", _field(row, "relation"), RELATIONS)
        _one_of("merge_policy", _field(row, "merge_policy"), MERGE_POLICIES)
        _matches("confidence", _field(row, "confidence"), CONFIDENCE_RE)
        _nonempty("evidence_type", _field(row, "evidence_type"))
        _nonempty("source_id", _field(row, "source_id"))
        return cls(
            relation_id=row["relation_id"],
            left_kind=row["left_kind"],
            left_id=row["left_id"],
            right_kind=row["right_kind"],
            right_id=row["right_id"],
            relation=row["relation"],
            merge_policy=row["merge_policy"],
            confidence=row["confidence"],
            evidence_type=row["evidence_type"],
            source_id=row["source_id"],
            evidence_id=row["evidence_id"],
            notes=row["notes"],
        )


@dataclass(frozen=True)
class ReviewCase:
    """One queued review item awaiting a human decision."""

    review_id: str
    subject_kind: str
    subject_id: str
    queue_reason: str
    suggested_relation: str
    source_id: str
    evidence_id: str
    notes: str

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> ReviewCase:
        _matches("review_id", _field(row, "review_id"), REVIEW_ID_RE)
        _one_of("subject_kind", _field(row, "subject_kind"), REVIEW_SUBJECT_KINDS)
        _nonempty("subject_id", _field(row, "subject_id"))
        _nonempty("queue_reason", _field(row, "queue_reason"))
        suggested = _field(row, "suggested_relation")
        if suggested and suggested not in RELATIONS:
            raise ValueError(f"suggested_relation: {suggested!r} not one of {sorted(RELATIONS)}")
        _nonempty("source_id", _field(row, "source_id"))
        return cls(
            review_id=row["review_id"],
            subject_kind=row["subject_kind"],
            subject_id=row["subject_id"],
            queue_reason=row["queue_reason"],
            suggested_relation=suggested,
            source_id=row["source_id"],
            evidence_id=row["evidence_id"],
            notes=row["notes"],
        )
