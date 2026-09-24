"""Verified content objects; namespace assignments and grants belong to the caller.

Publication is one directory rename. No mutable identity index can expose an
unfinished object, and reads derive catalog records from the verified manifest.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from .errors import ManifestError, ResolutionError
from .manifest import collect_package_files, load_manifest, package_digest, validate_manifest
from .packing import pack
from .references import URN, exact_digest, exact_version

LAYOUT = "objects-v1"
METADATA = "PAXLET-METADATA.json"
MAX_FILES = 10_000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}


def _no_symlinks(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ResolutionError(f"symlink is not permitted in store paths: {part}")


def get_store_dir() -> Path:
    """Return the configured root without creating or migrating anything."""
    custom = os.environ.get("PAXLET_STORE_DIR")
    path = Path(custom) if custom else Path(os.environ.get("PAXLET_HOME", Path.home() / ".paxlet")) / "store"
    path = Path(os.path.abspath(path.expanduser()))
    _no_symlinks(path)
    return path


def is_store_path(path: Path) -> bool:
    """Execution writes belong in an explicitly materialized workspace."""
    return path.resolve().is_relative_to(get_store_dir())


def _digest_hex(digest: str) -> str:
    # Bare hex remains a convenient lookup spelling; stored pins are canonical.
    if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
        digest = "sha256:" + digest
    if not isinstance(digest, str):
        raise ResolutionError("digest must be a string")
    exact_digest(digest)
    return digest.removeprefix("sha256:")


def _checked_package(root: Path, *, exact_inventory: bool) -> tuple[dict[str, Any], str, list[Path]]:
    _no_symlinks(root)
    if (root / METADATA).exists():
        raise ManifestError(f"{METADATA} is reserved for the archive envelope")
    _, manifest = load_manifest(root)
    result = validate_manifest(root, manifest)
    if not result.ok:
        raise ManifestError("invalid Paxlet package: " + "; ".join(result.errors))
    files = collect_package_files(root, manifest)
    size = 0
    if len(files) > MAX_FILES:
        raise ResolutionError("package exceeds file count limit")
    for file in files:
        info = file.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise ResolutionError("package contains a special or oversized file")
        size += info.st_size
    if size > MAX_PACKAGE_BYTES:
        raise ResolutionError("package exceeds total size limit")
    if exact_inventory:
        actual = set()
        for file in root.rglob("*"):
            if file.is_symlink() or not (file.is_file() or file.is_dir()):
                raise ResolutionError("package contains a symlink or special file")
            if file.is_file():
                actual.add(file)
        if actual != set(files):
            raise ResolutionError("package contains files outside the canonical inventory")
    return manifest, package_digest(root, manifest), files


def _copy_files(files: list[Path], source: Path, destination: Path) -> None:
    total = 0
    for file in files:
        target = destination / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        _no_symlinks(file)
        count = 0
        with file.open("rb") as src, target.open("xb") as dst:
            if not stat.S_ISREG(os.fstat(src.fileno()).st_mode):
                raise ResolutionError("source is not a regular file")
            while chunk := src.read(1024 * 1024):
                count += len(chunk)
                total += len(chunk)
                if count > MAX_FILE_BYTES or total > MAX_PACKAGE_BYTES:
                    raise ResolutionError("package grew beyond size limit during copy")
                dst.write(chunk)
        target.chmod(0o755 if file.stat().st_mode & 0o111 else 0o644)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResolutionError(f"duplicate archive metadata field: {key}")
        result[key] = value
    return result


def _archive_parts(name: str) -> list[str]:
    parts = name.split("/")
    if (len(name.encode("utf-8")) > 1024 or len(parts) > 32
            or "\\" in name or ":" in name or unicodedata.normalize("NFC", name) != name
            or any(not p or p in {".", ".."} or p.endswith((" ", "."))
                   or any(ord(c) < 32 or c in '<>"|?*' for c in p)
                   or p.split(".")[0].upper() in RESERVED_NAMES for p in parts)):
        raise ResolutionError(f"unsafe archive path: {name!r}")
    return parts


def _extract_archive(source: Path, destination: Path) -> tuple[dict[str, Any], str]:
    """Extract only bounded regular files with portable, unambiguous names."""
    _no_symlinks(source)
    if not source.is_file() or source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ResolutionError("archive is missing or exceeds size limit")
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > MAX_FILES + 1:
                raise ResolutionError("archive exceeds file count limit")
            names: set[str] = set()
            spellings: dict[str, str] = {}
            total = 0
            for member in members:
                name = member.filename
                parts = _archive_parts(name)
                mode = member.external_attr >> 16
                if name != member.orig_filename:
                    raise ResolutionError(f"unsafe archive path: {name!r}")
                for i in range(1, len(parts) + 1):
                    prefix = "/".join(parts[:i])
                    if spellings.setdefault(prefix.casefold(), prefix) != prefix:
                        raise ResolutionError("archive has case-aliased paths")
                    if len(spellings) > MAX_FILES + 1:
                        raise ResolutionError("archive exceeds file/directory count limit")
                folded = name.casefold()
                if folded in names:
                    raise ResolutionError(f"duplicate archive path: {name!r}")
                names.add(folded)
                if member.is_dir() or stat.S_IFMT(mode) not in {0, stat.S_IFREG} or member.flag_bits & 1:
                    raise ResolutionError("archive must contain unencrypted regular files only")
                total += member.file_size
                if member.file_size > MAX_FILE_BYTES or total > MAX_PACKAGE_BYTES:
                    raise ResolutionError("archive exceeds expanded size limit")
                if name == METADATA and member.file_size > 1024 * 1024:
                    raise ResolutionError("archive envelope exceeds size limit")
            # A file cannot also be another file's parent (including case aliases).
            for name in names:
                parts = name.split("/")
                if any("/".join(parts[:i]) in names for i in range(1, len(parts))):
                    raise ResolutionError("archive file/directory collision")
            if METADATA.casefold() not in names:
                raise ResolutionError("archive envelope is missing")
            for member in members:
                target = destination / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                count = 0
                with archive.open(member) as src, target.open("xb") as dst:
                    while chunk := src.read(1024 * 1024):
                        count += len(chunk)
                        if count > member.file_size or count > MAX_FILE_BYTES:
                            raise ResolutionError("archive member exceeds declared size")
                        dst.write(chunk)
                if count != member.file_size:
                    raise ResolutionError("archive member size mismatch")
                target.chmod(0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
            envelope = destination / METADATA
            metadata = json.loads(envelope.read_text(encoding="utf-8"), object_pairs_hook=_unique_json)
            envelope.unlink()
            manifest, digest, _ = _checked_package(destination, exact_inventory=True)
            if (not isinstance(metadata, dict) or set(metadata) != {"format", "identity", "package_digest"}
                    or metadata.get("format") != "paxlet-archive/0.1"
                    or metadata.get("identity") != manifest["identity"]
                    or metadata.get("package_digest") != digest):
                raise ResolutionError("archive envelope identity/digest mismatch")
            return manifest, digest
    except (OSError, ValueError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise ResolutionError(f"invalid Paxlet archive: {exc}") from exc


def _object_paths(hex_id: str) -> tuple[Path, Path, Path]:
    obj = get_store_dir() / LAYOUT / hex_id
    _no_symlinks(obj)
    return obj, obj / "package.paxlet.zip", obj / "package"


def _verify_object(hex_id: str) -> tuple[dict[str, Any], Path, Path]:
    obj, archive, package = _object_paths(hex_id)
    if not obj.is_dir() or {p.name for p in obj.iterdir()} != {"package", "package.paxlet.zip"}:
        raise ResolutionError("incomplete or malformed store object")
    manifest, digest, _ = _checked_package(package, exact_inventory=True)
    if digest != "sha256:" + hex_id:
        raise ResolutionError("stored package digest mismatch")
    # Verify the transport representation too; callers may replicate this archive.
    with tempfile.TemporaryDirectory(prefix="paxlet-verify-") as temp:
        _, archive_digest = _extract_archive(archive, Path(temp))
    if archive_digest != digest:
        raise ResolutionError("stored archive digest mismatch")
    return manifest, archive, package


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _seal_object(stage: Path) -> None:
    for file in stage.rglob("*"):
        if file.is_file():
            with file.open("rb") as stream:
                os.fsync(stream.fileno())
            file.chmod(0o555 if file.stat().st_mode & 0o111 else 0o444)
    for directory in sorted((p for p in stage.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        directory.chmod(0o555)
        _sync_directory(directory)
    _sync_directory(stage)


def put_package(source_path: str | Path, *, expected_digest: str | None = None) -> tuple[str, Path, Path]:
    """Verify in private staging, then atomically publish a complete content object.

    Conflicting namespace claims may coexist as bytes; selecting by URN fails on
    ambiguity. Only the node catalog can authorize an identity/version assignment.
    """
    exact_digest(expected_digest)
    source = Path(os.path.abspath(Path(source_path).expanduser()))
    _no_symlinks(source)
    objects = get_store_dir() / LAYOUT
    _no_symlinks(objects)
    if source.is_dir() and objects.is_relative_to(source):
        raise ResolutionError("store cannot be inside the source package")
    objects.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=objects) as temp:
            stage = Path(temp) / "object"
            package = stage / "package"
            package.mkdir(parents=True)
            if source.is_dir():
                _, original_digest, files = _checked_package(source, exact_inventory=False)
                _copy_files(files, source, package)
                _, digest, _ = _checked_package(package, exact_inventory=True)
                if digest != original_digest:
                    raise ResolutionError("source changed during installation")
            elif source.is_file() and source.name.endswith(".paxlet.zip"):
                _, digest = _extract_archive(source, package)
            else:
                raise ResolutionError(f"unsupported package format: {source}")
            if expected_digest is not None and digest != expected_digest:
                raise ResolutionError("package digest does not match installation pin")
            hex_id = _digest_hex(digest)
            obj, archive, unpacked = _object_paths(hex_id)
            if not obj.exists():
                pack(package, stage / "package.paxlet.zip")
                with tempfile.TemporaryDirectory(prefix="verify-", dir=temp) as verification:
                    if _extract_archive(stage / "package.paxlet.zip", Path(verification))[1] != digest:
                        raise ResolutionError("packed archive digest mismatch")
                _seal_object(stage)
                try:
                    # Existing nonempty objects are never replaced, even by races.
                    stage.rename(obj)
                except OSError:
                    if not obj.exists():
                        raise
                _sync_directory(objects)
            _verify_object(hex_id)
            return digest, archive, unpacked
    except OSError as exc:
        raise ResolutionError(f"cannot install package: {exc}") from exc


def has_package(digest: str) -> bool:
    """Missing is false; corrupt or invalid content raises, never counts as present."""
    return get_package("sha256:" + _digest_hex(digest)) is not None


def get_package(digest_or_urn: str, *, version: str | None = None) -> Path | None:
    """Return verified bytes. An ambiguous URN needs a version or a digest pin."""
    exact_version(version)
    if not isinstance(digest_or_urn, str):
        raise ResolutionError("package selector must be a digest or Paxlet URN")
    if not URN.fullmatch(digest_or_urn):
        hex_id = _digest_hex(digest_or_urn)
        obj, _, _ = _object_paths(hex_id)
        if not obj.exists():
            return None
        manifest, _, package = _verify_object(hex_id)
        if version is not None and manifest["identity"]["version"] != version:
            raise ResolutionError("stored package version mismatch")
        return package
    records = [record for record in list_packages() if record["urn"] == digest_or_urn
               and (version is None or record["version"] == version)]
    if len(records) > 1:
        raise ResolutionError("ambiguous stored package; select an exact version and/or digest")
    return Path(records[0]["path"]) if records else None


def list_packages() -> list[dict[str, Any]]:
    """Manifest-derived catalog projection; bindings are claims, not grants."""
    objects = get_store_dir() / LAYOUT
    _no_symlinks(objects)
    if not objects.exists():
        return []
    records = []
    for obj in sorted(objects.iterdir()):
        if obj.name.startswith(".staging-"):
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", obj.name):
            raise ResolutionError("invalid store object name")
        hex_id = _digest_hex(obj.name)
        manifest, archive, package = _verify_object(hex_id)
        records.append({
            "urn": manifest["identity"]["urn"], "version": manifest["identity"]["version"],
            "name": manifest["identity"]["name"],
            "digest": "sha256:" + hex_id, "archive": str(archive), "path": str(package),
            "bindings": manifest.get("bindings", []), "actions": manifest.get("actions", {}),
            "requires": manifest.get("requires", []), "permissions": manifest.get("permissions", {}),
            "dependencies": manifest.get("dependencies", {}),
        })
    return sorted(records, key=lambda r: (r["urn"], r["version"], r["digest"]))


def materialize_package(digest_or_urn: str, destination: str | Path, *, version: str | None = None) -> Path:
    """Create a new writable execution copy; never overwrite an existing workspace."""
    package = get_package(digest_or_urn, version=version)
    if package is None:
        raise ResolutionError("package not found in store")
    target = Path(os.path.abspath(Path(destination).expanduser()))
    _no_symlinks(target)
    if target.exists() or is_store_path(target):
        raise ResolutionError("execution destination must be new and outside the store")
    target.parent.mkdir(parents=True, exist_ok=True)
    _, digest, files = _checked_package(package, exact_inventory=True)
    if digest != "sha256:" + package.parent.name:
        raise ResolutionError("stored package changed before materialization")
    with tempfile.TemporaryDirectory(prefix=".paxlet-copy-", dir=target.parent) as temp:
        staged = Path(temp) / "package"
        staged.mkdir()
        _copy_files(files, package, staged)
        if _checked_package(staged, exact_inventory=True)[1] != digest:
            raise ResolutionError("stored package changed during materialization")
        # mkdir reserves the destination without clobbering even an empty dir.
        target.mkdir()
        try:
            staged.replace(target)
        except OSError:
            target.rmdir()
            raise
    return target
