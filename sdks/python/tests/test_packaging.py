"""Packaging gates: bundled rule tables must survive the trip into a wheel."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest

from tatar_names.data import release_path, rules_path

RULE_MARKERS: dict[str, list[str]] = {
    "transliteration_tt_latn.yaml": ["җ: c", 'ъ: ""'],
    "transliteration_ru_latn_passport.yaml": ["ъ: ie", "ж: zh"],
    "transliteration_tt_ru.yaml": ["җ: ж"],
    "confusables.yaml": ["do_not_merge:", "Ильмир"],
    "normalization.yaml": ["norm_001", "unicode_nfkc"],
}

# Runs in a throwaway venv whose cwd is outside the repo, so a pass proves the
# installed wheel itself carries the rule tables and not the release corpus.
INSTALLED_WHEEL_PROBE = """
from importlib.resources import files
from tatar_names.data import release_path, rules_path

RULE_MARKERS = {markers!r}

for name, markers in RULE_MARKERS.items():
    text = rules_path(name).read_text(encoding="utf-8")
    for marker in markers:
        assert marker in text, (name, marker)
    assert (files("tatar_names") / "rules" / name).is_file(), name

assert not release_path("identities.csv").exists()
print("wheel-ok")
""".format(markers=RULE_MARKERS)


@pytest.mark.parametrize(("name", "markers"), sorted(RULE_MARKERS.items()))
def test_bundled_rules_keep_known_content(name: str, markers: list[str]) -> None:
    text = rules_path(name).read_text(encoding="utf-8")
    for marker in markers:
        assert marker in text, (name, marker)


@pytest.mark.parametrize("name", sorted(RULE_MARKERS))
def test_rules_discoverable_via_importlib_resources(name: str) -> None:
    assert (files("tatar_names") / "rules" / name).is_file(), name


@pytest.fixture(scope="session")
def installed_wheel_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to build and install a wheel")
    scratch = tmp_path_factory.mktemp("wheel_gate")
    project_dir = Path(__file__).resolve().parents[1]
    out_dir = scratch / "dist"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    venv_dir = scratch / "venv"
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, capture_output=True)
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheels[0]), "--no-deps"],
        check=True,
        capture_output=True,
    )
    return python


def test_installed_wheel_carries_rules_but_not_corpus(
    installed_wheel_python: Path, tmp_path: Path
) -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [str(installed_wheel_python), "-c", INSTALLED_WHEEL_PROBE],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("wheel-ok")
