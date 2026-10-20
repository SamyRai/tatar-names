# GENERATED FILE - do not edit by hand.
# Regenerate with: python -m tatar_names.codegen
# Source of truth: schemas/*.schema.json (JSON Schema 2020-12).

from __future__ import annotations

VALID_ENTITY_TYPES = {"given", "surname"}
VALID_GENDERS = {"female", "male", "unisex", "unknown"}
VALID_STATUSES = {"active", "deprecated", "disputed"}
VALID_SCRIPTS = {"Cyrl", "Latn"}
VALID_FORM_KINDS = {"canonical", "normalized_source", "observed_variant", "transliterated"}
VALID_FORM_PROFILES = {
    "common_variant",
    "ru_adaptation",
    "ru_cyrl_to_latn_mvd_doc",
    "tt_cyrl_to_tt_latn_rt2013",
    "tt_original",
}
VALID_FORM_ROLES = {
    "common_observed",
    "official_ru_or_russified_primary",
    "official_tt",
    "passport_latin",
    "tt_latin_transliteration",
}
VALID_IDENTITY_STATUSES = {"alias", "canonical", "variant"}
VALID_MERGE_POLICIES = {"auto_merge", "candidate_only", "never_merge", "review_required"}
VALID_RELATIONS = {
    "near_confusable_but_distinct",
    "possible_variant",
    "review_candidate",
    "russified_primary_form",
    "same_etymon_but_distinct",
    "same_name_adapted_form",
    "same_name_official_pair",
    "same_name_script_variant",
    "tatarized_form_of_non_tatar_name",
}
VALID_LINK_KINDS = {"form", "name"}
VALID_REVIEW_SUBJECT_KINDS = {"excluded_entity", "form", "relation", "rule"}
