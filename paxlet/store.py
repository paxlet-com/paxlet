from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .errors import ManifestError, ResolutionError
from .manifest import load_manifest, package_digest, validate_manifest
from .packing import pack


def get_store_dir() -> Path:
    """Return root directory of the Paxlet content-addressed local store."""
    custom = os.environ.get("PAXLET_STORE_DIR")
    if custom:
        p = Path(custom).expanduser().resolve()
    else:
        p = Path(os.environ.get("PAXLET_HOME", Path.home() / ".paxlet")) / "store"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _digest_hex(digest: str) -> str:
    if digest.startswith("sha256:"):
        return digest.split(":", 1)[1]
    return digest


def put_package(source_path: str | Path) -> tuple[str, Path, Path]:
    """Store a Paxlet package in the content-addressed local store.

    Accepts either an unpacked directory or a .paxlet.zip archive.
    Returns (digest, archive_path, unpacked_path).
    """
    source = Path(source_path).resolve()
    if not source.exists():
        raise ResolutionError(f"package path does not exist: {source}")

    store_dir = get_store_dir()
    archives_dir = store_dir / "archives"
    packages_dir = store_dir / "packages"
    index_dir = store_dir / "index"
    for d in (archives_dir, packages_dir, index_dir):
        d.mkdir(parents=True, exist_ok=True)

    if source.is_file() and source.name.endswith(".paxlet.zip"):
        # Unpack to temporary directory to read manifest and calculate digest
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            with zipfile.ZipFile(source, "r") as zf:
                zf.extractall(temp_dir)
            manifest_file, manifest = load_manifest(temp_dir)
            digest = package_digest(temp_dir, manifest)
            hex_id = _digest_hex(digest)
            archive_dest = archives_dir / f"{hex_id}.paxlet.zip"
            if not archive_dest.exists():
                shutil.copy2(source, archive_dest)
            unpacked_dest = packages_dir / hex_id
            if not unpacked_dest.exists():
                shutil.copytree(temp_dir, unpacked_dest)
    elif source.is_dir():
        manifest_file, manifest = load_manifest(source)
        val = validate_manifest(source, manifest)
        if not val.ok:
            raise ManifestError("invalid Paxlet package: " + "; ".join(val.errors))
        digest = package_digest(source, manifest)
        hex_id = _digest_hex(digest)
        archive_dest = archives_dir / f"{hex_id}.paxlet.zip"
        if not archive_dest.exists():
            pack(source, archive_dest)
        unpacked_dest = packages_dir / hex_id
        if not unpacked_dest.exists():
            shutil.copytree(source, unpacked_dest)
    else:
        raise ResolutionError(f"unsupported package format: {source}")

    # Write index record
    identity = manifest.get("identity", {})
    urn = identity.get("urn", "unknown")
    version = identity.get("version", "unknown")
    urn_slug = "".join(ch if ch.isalnum() else "_" for ch in urn)
    index_file = index_dir / f"{urn_slug}@{version}.json"
    index_record = {
        "urn": urn,
        "version": version,
        "digest": digest,
        "archive": str(archive_dest),
        "path": str(unpacked_dest),
    }
    index_file.write_text(json.dumps(index_record, indent=2) + "\n", encoding="utf-8")

    return digest, archive_dest, unpacked_dest


def has_package(digest: str) -> bool:
    """Check if a package with the given digest exists in the store."""
    hex_id = _digest_hex(digest)
    return (get_store_dir() / "packages" / hex_id).is_dir()


def get_package(digest_or_urn: str) -> Path | None:
    """Retrieve the unpacked path of a stored package by digest or URN."""
    store_dir = get_store_dir()
    if digest_or_urn.startswith("sha256:") or len(digest_or_urn) == 64:
        hex_id = _digest_hex(digest_or_urn)
        target = store_dir / "packages" / hex_id
        return target if target.is_dir() else None

    # Search index by URN
    index_dir = store_dir / "index"
    if not index_dir.is_dir():
        return None
    for record_file in index_dir.glob("*.json"):
        try:
            data = json.loads(record_file.read_text(encoding="utf-8"))
            if data.get("urn") == digest_or_urn:
                target = Path(data.get("path", ""))
                if target.is_dir():
                    return target
        except (json.JSONDecodeError, OSError):
            continue
    return None


def list_packages() -> list[dict[str, Any]]:
    """List all packages currently stored in the content-addressed local store."""
    store_dir = get_store_dir()
    index_dir = store_dir / "index"
    if not index_dir.is_dir():
        return []
    records = []
    for record_file in sorted(index_dir.glob("*.json")):
        try:
            data = json.loads(record_file.read_text(encoding="utf-8"))
            records.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return records
