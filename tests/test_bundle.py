"""Verify the distributable uses the original independent protocol sources."""

import zipfile
from pathlib import Path

from scripts.build_integration import build_bundle


def test_bundle_is_self_contained_and_excludes_live_scanner_and_private_data(tmp_path):
    archive = build_bundle(tmp_path)
    with zipfile.ZipFile(archive) as bundle:
        prefix = "custom_components/wendougee_data/"
        names = bundle.namelist()
        assert prefix + "manifest.json" in names
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
