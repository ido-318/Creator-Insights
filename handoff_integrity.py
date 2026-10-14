import hashlib
import json
from pathlib import Path


HANDOFF_FILES = (
    "clean_data.csv",
    "dataset_contract.json",
)


def file_hash(path):
    """Calculate a SHA-256 fingerprint of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal_handoff(artifacts):
    """Record fingerprints when the analyst handoff is published."""
    artifacts = Path(artifacts)

    manifest = {
        "manifest_version": "1.0",
        "files": {
            filename: file_hash(artifacts / filename)
            for filename in HANDOFF_FILES
        },
    }

    (artifacts / "handoff_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    return manifest


def verify_handoff(artifacts):
    """Reject missing or changed files without updating fingerprints."""
    artifacts = Path(artifacts)

    manifest = json.loads(
        (artifacts / "handoff_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    if manifest.get("manifest_version") != "1.0":
        raise ValueError("Unsupported handoff manifest version.")

    recorded_files = manifest.get("files")

    if (
        not isinstance(recorded_files, dict)
        or set(recorded_files) != set(HANDOFF_FILES)
    ):
        raise ValueError("Invalid handoff manifest file list.")

    for filename in HANDOFF_FILES:
        path = artifacts / filename

        if not path.is_file():
            raise ValueError(f"Missing handoff file: {filename}")

        if file_hash(path) != recorded_files[filename]:
            raise ValueError(
                f"Handoff file changed after publication: {filename}"
            )

    return {"integrity_verified": True}