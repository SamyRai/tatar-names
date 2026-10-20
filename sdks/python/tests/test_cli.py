"""Exit-code and stderr contracts for the build, validate, and audit CLIs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tatar_names.cli import audit as audit_cli
from tatar_names.cli import build as build_cli
from tatar_names.cli import validate as validate_cli
from tatar_names.metadata import installed_version

from test_pipeline_data_safety import (
    attestation_row,
    entity_row,
    make_source_dir as write_source_fixture,
)


def simple_source(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    return write_source_fixture(
        base,
        [entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001")],
        [attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001")],
    )


def error_source(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    return write_source_fixture(
        base,
        [entity_row("ttn_000001", "Акмал", "Akmal", "ev_0000001")],
        [
            attestation_row("at_0000001", "ttn_000001", "Акмал", "ev_0000001"),
            # References an unknown entity, so source validation must fail.
            attestation_row("at_0000002", "ttn_999999", "Акмал", "ev_0000002"),
        ],
    )


def build_release_into(source_dir: Path, release_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_cli, "default_source_dir", lambda: source_dir)
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: release_dir)
    build_cli.main()


def exit_code(excinfo: pytest.ExceptionInfo[SystemExit]) -> int:
    # A SystemExit raised with a message string exits with status 1.
    code = excinfo.value.code
    return 1 if isinstance(code, str) else code


def test_validate_missing_source_dir_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        validate_cli.main(["--source-dir", str(tmp_path / "missing"), "--release-dir", str(tmp_path)])
    assert excinfo.value.code == 2
    assert "source directory not found" in capsys.readouterr().err


def test_validate_missing_release_dir_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = simple_source(tmp_path / "source")
    with pytest.raises(SystemExit) as excinfo:
        validate_cli.main(["--source-dir", str(source_dir), "--release-dir", str(tmp_path / "missing")])
    assert excinfo.value.code == 2
    assert "release directory not found" in capsys.readouterr().err


def test_validate_reports_error_rows_with_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = simple_source(tmp_path / "source")
    release_dir = tmp_path / "release"
    build_release_into(source_dir, release_dir, monkeypatch)

    with (release_dir / "forms.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fieldnames = list(rows[0])
    rows[0]["script"] = "Bogus"
    with (release_dir / "forms.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(SystemExit) as excinfo:
        validate_cli.main(["--source-dir", str(source_dir), "--release-dir", str(release_dir)])
    assert exit_code(excinfo) == 1
    assert "Dataset validation failed" in str(excinfo.value.code)


def test_validate_success_exits_0_and_quiet_suppresses_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_dir = simple_source(tmp_path / "source")
    release_dir = tmp_path / "release"
    build_release_into(source_dir, release_dir, monkeypatch)
    args = ["--source-dir", str(source_dir), "--release-dir", str(release_dir)]

    validate_cli.main(args)
    assert "OK" in capsys.readouterr().out

    validate_cli.main([*args, "--quiet"])
    assert capsys.readouterr().out == ""


def test_validate_success_on_committed_repository_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    validate_cli.main([])
    assert "OK" in capsys.readouterr().out


def test_build_missing_source_dir_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(build_cli, "default_source_dir", lambda: tmp_path / "missing")
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: tmp_path / "release")

    with pytest.raises(SystemExit) as excinfo:
        build_cli.main()

    assert excinfo.value.code == 2
    assert "source directory not found" in capsys.readouterr().err


def test_build_source_error_rows_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = error_source(tmp_path)
    monkeypatch.setattr(build_cli, "default_source_dir", lambda: source_dir)
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: tmp_path / "release")

    with pytest.raises(SystemExit) as excinfo:
        build_cli.main()

    assert exit_code(excinfo) == 1
    assert "Source validation failed" in str(excinfo.value.code)


def test_build_success_writes_deterministic_release_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = simple_source(tmp_path / "source")
    monkeypatch.setattr(build_cli, "default_source_dir", lambda: source_dir)
    monkeypatch.setattr(build_cli, "default_release_dir", lambda: tmp_path / "release")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1792454400")

    build_cli.main()

    release_dir = tmp_path / "release"
    croissant = json.loads((release_dir / "croissant.json").read_text(encoding="utf-8"))
    datapackage = json.loads((release_dir / "datapackage.json").read_text(encoding="utf-8"))
    version = installed_version()
    release_url = f"https://github.com/SamyRai/tatar-names/releases/tag/v{version}"
    expected_date = "2026-10-20T00:00:00Z"
    assert croissant["datePublished"] == expected_date
    assert croissant["url"] == release_url
    assert datapackage["resources"][0]["schema"] == (
        f"https://raw.githubusercontent.com/SamyRai/tatar-names/v{version}/schemas/tableschema/identities.tableschema.json"
    )
    first_run = {
        filename: (release_dir / filename).read_bytes()
        for filename in ("croissant.json", "datapackage.json")
    }

    build_cli.main()
    for filename, payload in first_run.items():
        assert (release_dir / filename).read_bytes() == payload


def test_audit_missing_release_dir_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = simple_source(tmp_path / "source")
    with pytest.raises(SystemExit) as excinfo:
        audit_cli.main(["--source-dir", str(source_dir), "--release-dir", str(tmp_path / "missing")])
    assert excinfo.value.code == 2
    assert "release directory not found" in capsys.readouterr().err


def test_audit_rejects_non_positive_sample_limit(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        audit_cli.main(["--sample-limit", "0"])
    assert excinfo.value.code == 2


def test_audit_success_prints_json_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_dir = simple_source(tmp_path / "source")
    release_dir = tmp_path / "release"
    build_release_into(source_dir, release_dir, monkeypatch)

    audit_cli.main([
        "--source-dir",
        str(source_dir),
        "--release-dir",
        str(release_dir),
        "--sample-limit",
        "1",
    ])

    report = json.loads(capsys.readouterr().out)
    assert isinstance(report, dict)
