"""Snapshot-cache guarantees for the resolver.

The perf regression guard is a work proxy: csv.reader is wrapped with a
counter, and a second resolve() on the same data_dir must perform zero CSV
reads. Wall-clock numbers live in benchmarks/bench_baseline.py.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tatar_names import resolve

IDENTITIES = """name_id,entity_type,gender,canonical_tt_cyrl,canonical_ru_cyrl,canonical_tt_latn,canonical_ru_latn,source_id,source_row,status,notes
ttn_000001,given,male,Айко,Айко,Ayko,Ayko,test,1,canonical,
ttn_000002,given,female,Айко,Айко,Ayko,Ayko,test,2,canonical,
"""

FORMS = """form_id,name_id,form,script,language_tag,form_role,identity_status,profile,confidence,source_id,evidence_id,merge_policy
f_0000001,ttn_000001,Айко,Cyrl,ru-Cyrl,official_ru_or_russified_primary,canonical,ru_adaptation,0.90,test,ev_1,candidate_only
f_0000002,ttn_000002,Айко,Cyrl,ru-Cyrl,official_tt,canonical,tt_original,0.95,test,ev_2,auto_merge
f_0000003,ttn_000001,Aiko,Latn,ru-Latn,passport_latin,variant,ru_cyrl_to_latn_mvd_doc,0.80,test,ev_3,auto_merge
"""

ALIASES = """alias_id,form_id,name_id,alias,script,language_tag,alias_type,method,confidence,merge_policy,source_id,rule_id
a_0000001,f_0000001,ttn_000001,Айчка,Cyrl,ru-Cyrl,common_variant,common_variant,0.85,candidate_only,test,
"""

RELATIONS = """relation_id,left_kind,left_id,right_kind,right_id,relation,merge_policy,confidence,evidence_type,source_id,evidence_id,notes
rel_0000001,name,ttn_000001,name,ttn_000002,near_confusable_but_distinct,never_merge,0.90,manual,test,ev_r1,identical spelling distinct persons
rel_0000002,name,ttn_000002,form,f_0000003,same_name_script_variant,auto_merge,0.95,manual,test,ev_r2,latin variant
rel_0000003,name,ttn_000001,form,f_0000001,same_name_official_pair,auto_merge,0.95,derived_identity_graph,test,ev_r3,mechanical same-identity edge
"""


def _write_release(root: Path) -> Path:
    release = root / "release"
    release.mkdir()
    (release / "identities.csv").write_text(IDENTITIES, encoding="utf-8")
    (release / "forms.csv").write_text(FORMS, encoding="utf-8")
    (release / "aliases.csv").write_text(ALIASES, encoding="utf-8")
    (release / "relations.csv").write_text(RELATIONS, encoding="utf-8")
    return release


@pytest.fixture(autouse=True)
def _isolated_cache() -> None:
    resolve.clear_resolver_cache()
    yield
    resolve.clear_resolver_cache()


def _counting_reader(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"count": 0}
    real_reader = csv.reader

    def counting_reader(*args: object, **kwargs: object) -> object:
        calls["count"] += 1
        return real_reader(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(csv, "reader", counting_reader)
    return calls


def test_first_resolve_reads_release_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _write_release(tmp_path)
    calls = _counting_reader(monkeypatch)

    result = resolve.resolve("Айко", release)

    assert calls["count"] > 0
    assert result["best_match"] is not None
    assert result["best_match"]["name_id"] == "ttn_000002"


def test_second_resolve_performs_zero_csv_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _write_release(tmp_path)
    calls = _counting_reader(monkeypatch)

    first = resolve.resolve("Айко", release)
    assert calls["count"] > 0

    reads_before = calls["count"]
    second = resolve.resolve("Айко", release)
    assert calls["count"] == reads_before
    assert second == first


def test_cold_and_warm_results_identical_across_query_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _write_release(tmp_path)
    _counting_reader(monkeypatch)

    for query in ("Айко", "Айчка", "zzzqqq"):
        resolve.clear_resolver_cache()
        cold = resolve.resolve(query, release)
        warm = resolve.resolve(query, release)
        assert cold == warm


def test_clear_resolver_cache_forces_rebuild(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _write_release(tmp_path)
    calls = _counting_reader(monkeypatch)

    resolve.resolve("Айко", release)
    resolve.resolve("Айко", release)
    reads_before = calls["count"]

    resolve.clear_resolver_cache()
    resolve.resolve("Айко", release)

    assert calls["count"] > reads_before


def test_unknown_data_dir_builds_its_own_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _write_release(tmp_path)
    other = tmp_path / "other-release"
    other.mkdir()
    (other / "identities.csv").write_text(IDENTITIES, encoding="utf-8")
    (other / "forms.csv").write_text(
        "form_id,name_id,form,script,language_tag,form_role,identity_status,profile,confidence,source_id,evidence_id,merge_policy\n"
        "f_0000009,ttn_000001,Айко,Cyrl,ru-Cyrl,official_tt,canonical,tt_original,0.70,test,ev_9,never_merge\n",
        encoding="utf-8",
    )
    (other / "aliases.csv").write_text("alias_id,form_id,name_id,alias,script,language_tag,alias_type,method,confidence,merge_policy,source_id,rule_id\n", encoding="utf-8")
    (other / "relations.csv").write_text("relation_id,left_kind,left_id,right_kind,right_id,relation,merge_policy,confidence,evidence_type,source_id,evidence_id,notes\n", encoding="utf-8")
    calls = _counting_reader(monkeypatch)

    first = resolve.resolve("Айко", release)
    reads_before = calls["count"]
    second = resolve.resolve("Айко", other)

    assert calls["count"] > reads_before
    assert second != first
    assert second["best_match"]["name_id"] == "ttn_000001"
    assert second["best_match"]["merge_policy"] == "never_merge"


def test_snapshot_excludes_mechanically_derived_edges(tmp_path: Path) -> None:
    release = _write_release(tmp_path)

    snapshot = resolve._snapshot_for(release)

    # TN-17: derived same-identity edges remain in relations.csv for
    # consumers but never enter the internal lookup index.
    assert set(snapshot.relations_by_name) == {"ttn_000001", "ttn_000002"}
    assert all(
        relation["evidence_type"] != "derived_identity_graph"
        for rows in snapshot.relations_by_name.values()
        for relation in rows
    )
