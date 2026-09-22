"""Verify the distributable uses the original independent protocol sources."""

import json
import tomllib
import zipfile
from pathlib import Path

from scripts.build_integration import build_bundle


def test_bundle_is_self_contained_and_excludes_live_scanner_and_private_data(tmp_path):
    archive = build_bundle(tmp_path)
    with zipfile.ZipFile(archive) as bundle:
        prefix = "custom_components/wendougee_data/"
        names = bundle.namelist()
        assert prefix + "manifest.json" in names
        assert prefix + "services.yaml" in names
        assert prefix + "images/wendougee-data-s-white-rose-gold.png" in names
        assert prefix + "_protocol/controls.py" in names
        assert prefix + "_protocol/session.py" in names
        assert prefix + "_protocol/live.py" not in names
        for name in names:
            assert "__pycache__" not in name
            assert "research/" not in name
            assert not name.endswith((".log", ".pcap", ".pyc"))
        assert (
            bundle.read(prefix + "_protocol/session.py")
            == Path("src/wendougee_data/session.py").read_bytes()
        )
        assert (
            bundle.read(prefix + "_protocol/controls.py")
            == Path("src/wendougee_data/controls.py").read_bytes()
        )


def test_public_names_and_versions_are_consistent():
    manifest = json.loads(
        Path("custom_components/wendougee_data/manifest.json").read_text()
    )
    project = tomllib.loads(Path("pyproject.toml").read_text())
    hacs = json.loads(Path("hacs.json").read_text())

    assert manifest["name"] == "WENDOUGEE DATA S"
    assert hacs["name"] == manifest["name"]
    assert project["project"]["version"] == manifest["version"]
