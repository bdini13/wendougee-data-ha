"""Bundle our independent protocol sources; no external code or network access."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "wendougee_data"
PROTOCOL_FILES = (
    "__init__.py",
    "const.py",
    "controls.py",
    "crc.py",
    "modbus.py",
    "reads.py",
    "session.py",
    "state.py",
    "telemetry.py",
)


def prepare_protocol() -> None:
    """Generate only the named owned files; never copy the standalone scanner."""
    target = COMPONENT / "_protocol"
    target.mkdir(exist_ok=True)
    for name in PROTOCOL_FILES:
        (target / name).write_bytes((ROOT / "src/wendougee_data" / name).read_bytes())


def build_bundle(destination: Path) -> Path:
    """Create an installable zip with an explicit source-file allowlist."""
    prepare_protocol()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "wendougee_data.zip"
    sources = sorted(COMPONENT.glob("*.py")) + sorted(COMPONENT.glob("*.json"))
    sources += sorted(COMPONENT.glob("*.yaml"))
    sources += sorted((COMPONENT / "translations").glob("*.json"))
    sources += sorted((COMPONENT / "images").glob("*.png"))
    sources += [COMPONENT / "_protocol" / name for name in PROTOCOL_FILES]
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for path in sources:
            bundle.write(path, path.relative_to(ROOT))
        bundle.write(ROOT / "LICENSE", "custom_components/wendougee_data/LICENSE")
    return archive


if __name__ == "__main__":
    print(build_bundle(ROOT / "dist"))
