from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ManifestError

MANIFEST_NAME = "paxlet.json"
CORE_VERSION = "0.1"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def manifest_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_dir():
        candidate = candidate / MANIFEST_NAME
    return candidate.resolve()


def load_manifest(path: str | Path) -> tuple[Path, dict[str, Any]]:
    target = manifest_path(path)
    if not target.exists():
        raise ManifestError(f"manifest not found: {target}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be an object")
    return target, data


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith(("/", "\\")):
        raise ManifestError(f"path must be a non-empty relative path: {relative!r}")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ManifestError(f"path escapes package root: {relative}") from exc
    return resolved


def _validate_schema_fragment(fragment: Any, label: str, errors: list[str]) -> None:
    if fragment is None:
        return
    if not isinstance(fragment, dict):
        errors.append(f"{label} must be an object")
        return
    if "type" in fragment and fragment["type"] not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
        errors.append(f"{label}.type is not a supported JSON type")
    if fragment.get("type") == "object" and "properties" in fragment and not isinstance(fragment["properties"], dict):
        errors.append(f"{label}.properties must be an object")
    if "required" in fragment and not (isinstance(fragment["required"], list) and all(isinstance(v, str) for v in fragment["required"])):
        errors.append(f"{label}.required must be an array of strings")


def validate_manifest(package_dir: Path, data: dict[str, Any], check_files: bool = True) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("paxlet") != CORE_VERSION:
        errors.append(f"paxlet must be {CORE_VERSION!r}")

    identity = data.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity must be an object")
    else:
        urn = identity.get("urn")
        if not isinstance(urn, str) or not urn.startswith("urn:paxlet:"):
            errors.append("identity.urn must start with 'urn:paxlet:'")
        for field in ("name", "version"):
            if not isinstance(identity.get(field), str) or not identity[field].strip():
                errors.append(f"identity.{field} must be a non-empty string")

    bindings = data.get("bindings", [])
    if not isinstance(bindings, list) or not all(isinstance(v, str) and ":" in v for v in bindings):
        errors.append("bindings must be an array of URI strings")

    actions = data.get("actions", {})
    resources = data.get("resources", [])
    if not isinstance(actions, dict):
        errors.append("actions must be an object")
        actions = {}
    if not isinstance(resources, list) or not all(isinstance(v, str) for v in resources):
        errors.append("resources must be an array of relative paths")
        resources = []
    if not actions and not resources:
        errors.append("a Paxlet must contain at least one action or resource")

    for name, action in actions.items():
        label = f"actions.{name}"
        if not isinstance(name, str) or not name.strip():
            errors.append("action names must be non-empty strings")
            continue
        if not isinstance(action, dict):
            errors.append(f"{label} must be an object")
            continue
        runtime = action.get("runtime")
        if not isinstance(runtime, dict):
            errors.append(f"{label}.runtime must be an object")
            continue
        runtime_type = runtime.get("type")
        if runtime_type not in {"python", "command"}:
            errors.append(f"{label}.runtime.type must be 'python' or 'command'")
        if runtime_type == "python":
            entry = runtime.get("entry")
            if not isinstance(entry, str):
                errors.append(f"{label}.runtime.entry must be a relative path")
            else:
                try:
                    path = safe_path(package_dir, entry)
                    if check_files and not path.is_file():
                        errors.append(f"{label}.runtime.entry not found: {entry}")
                except ManifestError as exc:
                    errors.append(str(exc))
        if runtime_type == "command":
            argv = runtime.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                errors.append(f"{label}.runtime.argv must be a non-empty string array")
        _validate_schema_fragment(action.get("input"), f"{label}.input", errors)
        _validate_schema_fragment(action.get("output"), f"{label}.output", errors)

    for resource in resources:
        try:
            path = safe_path(package_dir, resource)
            if check_files and not path.exists():
                errors.append(f"resource not found: {resource}")
        except ManifestError as exc:
            errors.append(str(exc))

    requires = data.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(v, str) and v.startswith("urn:paxlet:") for v in requires):
        errors.append("requires must be an array of Paxlet URNs")

    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        errors.append("permissions must be an object")
    else:
        fs = permissions.get("filesystem", {})
        if not isinstance(fs, dict):
            errors.append("permissions.filesystem must be an object")
        else:
            for mode in ("read", "write"):
                vals = fs.get(mode, [])
                if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
                    errors.append(f"permissions.filesystem.{mode} must be an array of strings")
        for key in ("network", "secrets"):
            vals = permissions.get(key, [])
            if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
                errors.append(f"permissions.{key} must be an array of strings")

    provenance = data.get("provenance", {})
    if provenance is not None and not isinstance(provenance, dict):
        errors.append("provenance must be an object")

    if permissions.get("network"):
        warnings.append("reference runtime declares network permissions but does not enforce a network sandbox")
    if isinstance(permissions.get("filesystem"), dict) and permissions["filesystem"].get("write"):
        warnings.append("reference runtime declares filesystem write permissions but does not enforce an OS sandbox")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def collect_package_files(package_dir: Path, data: dict[str, Any]) -> list[Path]:
    root = package_dir.resolve()
    files: set[Path] = {root / MANIFEST_NAME}
    for action in data.get("actions", {}).values():
        runtime = action.get("runtime", {}) if isinstance(action, dict) else {}
        if runtime.get("type") == "python" and isinstance(runtime.get("entry"), str):
            files.add(safe_path(root, runtime["entry"]))
    for relative in data.get("resources", []):
        path = safe_path(root, relative)
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    files.add(child.resolve())
        else:
            files.add(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def package_digest(package_dir: Path, data: dict[str, Any]) -> str:
    root = package_dir.resolve()
    digest = hashlib.sha256()
    for path in collect_package_files(root, data):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()
