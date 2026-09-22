from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from .errors import ResolutionError
from .manifest import package_digest

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "registry" / "local.json"


def load_registry(path: str | Path | None = None) -> tuple[Path, dict]:
    target = Path(path).expanduser().resolve() if path else DEFAULT_REGISTRY
    if not target.exists():
        raise ResolutionError(f"registry not found: {target}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResolutionError(f"invalid registry JSON: {exc}") from exc
    if data.get("registry") != "paxlet/0.1" or not isinstance(data.get("entries"), dict):
        raise ResolutionError("unsupported registry format")
    return target, data


def resolve(
    urn: str,
    registry_path: str | Path | None = None,
    version: str | None = None,
) -> list[dict]:
    target, data = load_registry(registry_path)
    entries = data["entries"].get(urn, [])
    if not entries:
        raise ResolutionError(f"URN not found: {urn}")
    out: list[dict] = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("uri"), str):
            continue
        if version and item.get("version") != version:
            continue
        uri = item["uri"]
        parsed = urlparse(uri)
        if parsed.scheme == "file" and not parsed.netloc:
            raw_path = unquote(parsed.path)
            p = Path(raw_path)
            if not p.is_absolute():
                p = (target.parent / p).resolve()
            uri = p.as_uri()
        out.append({**item, "uri": uri})
    if not out:
        msg = f"URN {urn} has no usable locations" + (f" matching version {version}" if version else "")
        raise ResolutionError(msg)
    return out


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ResolutionError(f"reference runtime can execute only file: locations, got {parsed.scheme or 'no scheme'}")
    if parsed.netloc not in ("", "localhost"):
        raise ResolutionError("remote file:// hosts are not supported")
    return Path(unquote(parsed.path)).resolve()


def resolve_to_path(
    urn: str,
    registry_path: str | Path | None = None,
    *,
    version: str | None = None,
    verify_digest: bool = True,
) -> Path:
    locations = resolve(urn, registry_path, version=version)
    for item in locations:
        try:
            path = uri_to_path(item["uri"])
            if verify_digest and item.get("digest"):
                expected = item["digest"]
                actual = package_digest(path)
                if actual != expected:
                    raise ResolutionError(
                        f"package digest mismatch for {urn} at {path}: expected {expected}, got {actual}"
                    )
            return path
        except ResolutionError:
            raise
        except Exception:
            continue
    raise ResolutionError(f"no executable file: location for {urn}")
