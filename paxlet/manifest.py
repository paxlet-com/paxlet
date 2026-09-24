from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ManifestError, ResolutionError
from .references import NAME, URN, exact_version, validate_binding

MANIFEST_NAME = "paxlet.json"
CORE_VERSION = "0.1"

IGNORED_DIR_NAMES = {
    ".paxlet",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
}
IGNORED_FILE_PATTERNS = {".DS_Store", "Thumbs.db"}
IGNORED_EXTENSIONS = {".pyc", ".pyo", ".paxlet.zip"}


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


def _manifest_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate manifest field: {key}")
        result[key] = value
    return result


def _invalid_json_constant(value: str):
    raise ManifestError(f"non-finite JSON number is not permitted: {value}")


def load_manifest(path: str | Path) -> tuple[Path, dict[str, Any]]:
    target = manifest_path(path)
    if not target.exists():
        raise ManifestError(f"manifest not found: {target}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=_manifest_fields,
                          parse_constant=_invalid_json_constant)
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        raise ManifestError(f"invalid JSON in {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be an object")
    return target, data


def safe_path(root: Path, relative: str, allow_symlinks: bool = False) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith(("/", "\\")):
        raise ManifestError(f"path must be a non-empty relative path: {relative!r}")
    resolved_root = root.resolve()
    target = resolved_root / relative
    if not allow_symlinks:
        check = target
        while check != resolved_root and check != check.parent:
            if check.is_symlink():
                raise ManifestError(f"symlinks are not permitted in Paxlet packages: {relative}")
            check = check.parent
    resolved = target.resolve()
    if not allow_symlinks and resolved.is_symlink():
        raise ManifestError(f"symlinks are not permitted in Paxlet packages: {relative}")
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
    if "type" in fragment and fragment["type"] not in ("object", "array", "string", "number", "integer", "boolean", "null"):
        errors.append(f"{label}.type is not a supported JSON type")
    if fragment.get("type") == "object" and "properties" in fragment and not isinstance(fragment["properties"], dict):
        errors.append(f"{label}.properties must be an object")
    if "required" in fragment and not (isinstance(fragment["required"], list) and all(isinstance(v, str) for v in fragment["required"])):
        errors.append(f"{label}.required must be an array of strings")


def validate_manifest(package_dir: Path, data: dict[str, Any], check_files: bool = True) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if check_files and package_dir.exists() and package_dir.is_dir():
        for child in package_dir.rglob("*"):
            if child.is_symlink():
                errors.append(f"symlinks are not permitted in Paxlet packages: {child.relative_to(package_dir).as_posix()}")

    if data.get("paxlet") != CORE_VERSION:
        errors.append(f"paxlet must be {CORE_VERSION!r}")

    identity = data.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity must be an object")
    else:
        urn = identity.get("urn")
        if not isinstance(urn, str) or not URN.fullmatch(urn):
            errors.append("identity.urn must be a canonical Paxlet URN")
        for field in ("name", "version"):
            if not isinstance(identity.get(field), str) or not identity[field].strip():
                errors.append(f"identity.{field} must be a non-empty string")
        try:
            exact_version(identity.get("version"))
        except ResolutionError as exc:
            errors.append(str(exc))

    bindings = data.get("bindings", [])
    if not isinstance(bindings, list):
        errors.append("bindings must be an array of package URI strings")
    else:
        for binding in bindings:
            try:
                validate_binding(binding)
            except ResolutionError as exc:
                errors.append(f"invalid package binding: {exc}")
        if len({v for v in bindings if isinstance(v, str)}) != len(bindings):
            errors.append("bindings must be unique URI strings")

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
        if not isinstance(name, str) or not re.fullmatch(NAME, name):
            errors.append("action names must be canonical address names")
            continue
        if not isinstance(action, dict):
            errors.append(f"{label} must be an object")
            continue
        runtime = action.get("runtime")
        if not isinstance(runtime, dict):
            errors.append(f"{label}.runtime must be an object")
            continue
        runtime_type = runtime.get("type")
        if runtime_type not in ("python", "command"):
            errors.append(f"{label}.runtime.type must be 'python' or 'command'")
        if runtime_type == "python":
            entry = runtime.get("entry")
            if not isinstance(entry, str) or not entry.strip():
                errors.append(f"{label}.runtime.entry must be a non-empty relative path")
            else:
                try:
                    path = safe_path(package_dir, entry)
                    if check_files and not path.is_file():
                        errors.append(f"{label}.runtime.entry not found: {entry}")
                except ManifestError as exc:
                    errors.append(str(exc))
        if runtime_type == "command":
            argv = runtime.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v.strip() for v in argv):
                errors.append(f"{label}.runtime.argv must be a non-empty string array")
            else:
                first = argv[0]
                is_local = first.startswith("./") or (not first.startswith("/") and (package_dir / first).is_file())
                if not is_local:
                    declared_tools = set()
                    for container, key in [(data.get("permissions", {}), "host_tools"),
                                           (data.get("dependencies", {}), "host"),
                                           (runtime, "host_dependencies"), (runtime, "tools")]:
                        values = container.get(key, []) if isinstance(container, dict) else []
                        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                            errors.append(f"{label}: {key} must be an array of strings")
                        else:
                            declared_tools.update(values)
                    if first not in declared_tools:
                        errors.append(
                            f"{label}.runtime.argv[0] references undeclared host executable {first!r}; "
                            f"declare it in permissions.host_tools or dependencies.host"
                        )
                if check_files:
                    for arg in argv:
                        clean_arg = arg[2:] if arg.startswith("./") else arg
                        if arg.startswith("./") or (not arg.startswith("/") and (package_dir / clean_arg).is_file()):
                            try:
                                arg_path = safe_path(package_dir, clean_arg)
                                if not arg_path.is_file():
                                    errors.append(f"{label}.runtime.argv references missing file: {arg}")
                            except ManifestError as exc:
                                errors.append(str(exc))
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

    dependencies = data.get("dependencies", {})
    if dependencies is not None and not isinstance(dependencies, dict):
        errors.append("dependencies must be an object")
    elif isinstance(dependencies, dict):
        for dep_key in ("host", "paxlet"):
            vals = dependencies.get(dep_key, [])
            if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
                errors.append(f"dependencies.{dep_key} must be an array of strings")

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
        for key in ("network", "secrets", "host_tools"):
            vals = permissions.get(key, [])
            if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
                errors.append(f"permissions.{key} must be an array of strings")

    provenance = data.get("provenance", {})
    if provenance is not None and not isinstance(provenance, dict):
        errors.append("provenance must be an object")

    if not isinstance(permissions, dict):
        permissions = {}
    if permissions.get("network"):
        warnings.append("reference runtime declares network permissions but does not enforce a network sandbox")
    if isinstance(permissions.get("filesystem"), dict) and permissions["filesystem"].get("write"):
        warnings.append("reference runtime declares filesystem write permissions but does not enforce an OS sandbox")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def collect_package_files(package_dir: Path, data: dict[str, Any]) -> list[Path]:
    root = package_dir.resolve()
    files: set[Path] = set()
    if (root / "PAXLET-METADATA.json").exists():
        raise ManifestError("PAXLET-METADATA.json is reserved for the archive envelope")

    manifest_target = root / MANIFEST_NAME
    if manifest_target.is_file():
        if manifest_target.is_symlink():
            raise ManifestError(f"symlinks are not permitted in Paxlet packages: {MANIFEST_NAME}")
        files.add(manifest_target)

    for action in data.get("actions", {}).values():
        if not isinstance(action, dict):
            continue
        runtime = action.get("runtime", {})
        if not isinstance(runtime, dict):
            continue
        if runtime.get("type") == "python" and isinstance(runtime.get("entry"), str):
            p = safe_path(root, runtime["entry"])
            if p.is_file():
                files.add(p)
        elif runtime.get("type") == "command" and isinstance(runtime.get("argv"), list):
            for arg in runtime["argv"]:
                if isinstance(arg, str):
                    clean_arg = arg[2:] if arg.startswith("./") else arg
                    candidate = root / clean_arg
                    if candidate.is_file():
                        files.add(safe_path(root, clean_arg))

    for relative in data.get("resources", []):
        path = safe_path(root, relative)
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_symlink():
                    raise ManifestError(f"symlinks are not permitted in Paxlet packages: {child.relative_to(root).as_posix()}")
                if child.is_file():
                    files.add(child.resolve())
        elif path.is_file():
            files.add(path)

    # Complete package closure: all non-ignored local package implementation files
    if root.is_dir():
        for item in root.rglob("*"):
            if item.is_symlink():
                raise ManifestError(f"symlinks are not permitted in Paxlet packages: {item.relative_to(root).as_posix()}")
            rel_parts = item.relative_to(root).parts
            if any(part in IGNORED_DIR_NAMES for part in rel_parts):
                continue
            if item.is_file():
                if item.name in IGNORED_FILE_PATTERNS or any(item.name.endswith(suffix) for suffix in IGNORED_EXTENSIONS):
                    continue
                files.add(item.resolve())

    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def package_digest(package_dir: Path, data: dict[str, Any] | None = None) -> str:
    root = package_dir.resolve()
    if data is None:
        _, data = load_manifest(root)
    digest = hashlib.sha256()
    for path in collect_package_files(root, data):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()
