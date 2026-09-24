from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .errors import ManifestError, ResolutionError
from .manifest import load_manifest, package_digest, validate_manifest
from .references import URN, exact_digest, exact_version, parse_reference, validate_binding, validate_uri

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "registry" / "local.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResolutionError(f"duplicate registry key: {key}")
        result[key] = value
    return result


def load_registry(path: str | Path | None = None) -> tuple[Path, dict]:
    target = Path(path).expanduser().resolve() if path else DEFAULT_REGISTRY
    try:
        data = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResolutionError(f"cannot read registry: {exc}") from exc
    if not isinstance(data, dict) or data.get("registry") != "paxlet/0.1" or not isinstance(data.get("entries"), dict):
        raise ResolutionError("unsupported registry format")
    aliases = data.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ResolutionError("registry aliases must map package bindings to URNs")
    for alias, urn in aliases.items():
        validate_binding(alias)
        if alias.startswith("urn:") or not isinstance(urn, str) or not URN.fullmatch(urn) or urn not in data["entries"]:
            raise ResolutionError("alias must point directly to a registered Paxlet URN")
        if alias in data["entries"]:
            raise ResolutionError(f"conflicting alias and entry: {alias}")
    return target, data


def _selection(reference, registry_path, version):
    ref = parse_reference(reference)
    exact_version(version)
    if ref.version and version and ref.version != version:
        raise ResolutionError("conflicting version selectors")
    version = version or ref.version
    target, data = load_registry(registry_path)
    urn = ref.package if URN.fullmatch(ref.package) else data.get("aliases", {}).get(ref.package)
    if not urn:
        raise ResolutionError(f"package alias is not registered: {ref.package}")
    entries = data["entries"].get(urn)
    if not isinstance(entries, list) or not entries:
        raise ResolutionError(f"URN not found or has invalid locations: {urn}")
    out = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("uri"), str) or not isinstance(item.get("version"), str):
            raise ResolutionError("registry locations require uri and exact version")
        exact_version(item["version"])
        exact_digest(item.get("digest"))
        if version is not None and item["version"] != version:
            continue
        validate_uri(item["uri"])
        parsed = urlsplit(item["uri"])
        uri = item["uri"]
        if parsed.scheme == "file" and ("?" in uri or "#" in uri or not parsed.path):
            raise ResolutionError("file: locations require a path without query or fragment")
        if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
            uri = uri_to_path(uri, base=target.parent).as_uri()
        out.append({**item, "uri": uri})
    if not out:
        raise ResolutionError(f"URN {urn} has no locations matching version {version}")
    return ref, urn, out


def resolve(reference: str, registry_path: str | Path | None = None, version: str | None = None) -> list[dict]:
    """Return declared locations; this inventory neither executes nor verifies bytes."""
    return _selection(reference, registry_path, version)[2]


def uri_to_path(uri: str, *, base: Path | None = None) -> Path:
    validate_uri(uri)
    parsed = urlsplit(uri)
    if parsed.scheme != "file":
        raise ResolutionError(f"reference runtime supports only file: locations, got {parsed.scheme}")
    if parsed.netloc not in ("", "localhost"):
        raise ResolutionError("remote file:// hosts are not supported")
    if "?" in uri or "#" in uri or not parsed.path:
        raise ResolutionError("file: locations require a path without query or fragment")
    try:
        raw = unquote(parsed.path, errors="strict")
    except UnicodeError as exc:
        raise ResolutionError("invalid file URI encoding") from exc
    if any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ResolutionError("file URI contains control characters")
    path = Path(raw)
    return ((base or Path.cwd()) / path).resolve()


@dataclass(frozen=True)
class ResolvedPackage:
    package: str
    action: str | None
    version: str
    digest: str
    path: Path

    def plan(self) -> dict:
        """Portable execution selection; local paths and input are kept separate."""
        return {"package": self.package, "action": self.action, "version": self.version, "digest": self.digest}


def resolve_package(
    reference: str,
    registry_path: str | Path | None = None,
    *,
    version: str | None = None,
    action: str | None = None,
    digest: str | None = None,
) -> ResolvedPackage:
    """Resolve and verify local mirrors without running any package code."""
    exact_digest(digest)
    ref, urn, locations = _selection(reference, registry_path, version)
    if ref.action and action and ref.action != action:
        raise ResolutionError("conflicting action selectors")
    action = action or ref.action
    versions = {item["version"] for item in locations}
    if len(versions) != 1:
        raise ResolutionError("multiple package versions; select an exact version")
    selected_version = next(iter(versions))
    digests = {item["digest"] for item in locations if item.get("digest") is not None}
    if digest is not None:
        digests.add(digest)
    if len(digests) > 1:
        raise ResolutionError("conflicting package digests for the selected version")
    expected = next(iter(digests), None)
    selected = None
    for item in locations:
        location = urlsplit(item["uri"])
        if location.scheme != "file" or location.netloc not in ("", "localhost"):
            continue
        path = uri_to_path(item["uri"])
        if not path.exists():
            continue
        try:
            manifest_file, manifest = load_manifest(path)
            path = manifest_file.parent
            result = validate_manifest(path, manifest)
            if not result.ok:
                raise ResolutionError("invalid resolved manifest: " + "; ".join(result.errors))
            identity = manifest["identity"]
            if identity["urn"] != urn or identity["version"] != selected_version:
                raise ResolutionError("resolved manifest identity/version does not match registry request")
            if ref.package != urn and ref.package not in manifest.get("bindings", []):
                raise ResolutionError("resolved manifest does not declare the registered package alias")
            if action is not None and action not in manifest.get("actions", {}):
                raise ResolutionError(f"action not found: {action}")
            actual = package_digest(path, manifest)
        except (OSError, UnicodeError, ManifestError) as exc:
            raise ResolutionError(f"cannot verify local package: {exc}") from exc
        if expected is not None and actual != expected:
            raise ResolutionError(f"package digest mismatch for {urn}: expected {expected}, got {actual}")
        if selected is not None and actual != selected.digest:
            raise ResolutionError("conflicting local package contents for the selected version")
        selected = selected or ResolvedPackage(urn, action, selected_version, actual, path)
    if selected is None:
        raise ResolutionError(f"no executable file: location for {urn}")
    return selected


def resolve_to_path(
    reference: str,
    registry_path: str | Path | None = None,
    *,
    version: str | None = None,
    verify_digest: bool = True,
) -> Path:
    if not verify_digest:
        raise ResolutionError("digest verification cannot be disabled for resolved packages")
    return resolve_package(reference, registry_path, version=version).path
