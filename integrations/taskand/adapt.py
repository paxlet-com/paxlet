from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paxlet.manifest import validate_manifest


def semver_from_taskand_version(v_str: str) -> str:
    """Convert Taskand v-tags (e.g. v1, v2, v1.2) to semver (e.g. 1.0.0, 2.0.0)."""
    v = v_str.strip().lstrip("v")
    parts = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def parse_taskand_uri(uri: str) -> dict[str, str]:
    """Extract authority, organism, capability, and version from proc:// URI."""
    m = re.fullmatch(r"proc://(taskand\.dev)/([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)/(v(?:0|[1-9][0-9]*))", uri)
    if not m:
        raise ValueError("expected canonical Taskand proc://taskand.dev/organism/capability/vN URI")
    return {"host": m[1], "organism": m[2], "capability": m[3], "version": m[4]}


def adapt_proc_yaml(
    proc_yaml_path: Path | str,
    output_file: Path | str | None = None,
    write: bool = True,
) -> tuple[dict[str, Any], bool, list[str]]:
    """Convert a Taskand proc.yaml into a standard Paxlet manifest (paxlet.json)."""
    proc_yaml_path = Path(proc_yaml_path).resolve()
    proc_dir = proc_yaml_path.parent

    try:
        import yaml
        raw_data = yaml.safe_load(proc_yaml_path.read_text(encoding="utf-8")) or {}
    except ImportError:
        raw_data = {}
        for line in proc_yaml_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                raw_data[k.strip()] = v.strip().strip('"').strip("'")

    if not isinstance(raw_data, dict):
        raise ValueError("proc.yaml must contain a mapping")
    uri = raw_data.get("uri")
    if not isinstance(uri, str):
        raise ValueError("proc.yaml requires a process URI")
    parsed_uri = parse_taskand_uri(uri)
    organism = parsed_uri["organism"]
    if raw_data.get("organism", organism) != organism:
        raise ValueError("proc.yaml organism does not match process URI")
    # A descriptive capability field must never rename the URI's identity.
    capability = parsed_uri["capability"]
    v_tag = parsed_uri.get("version", "v1")
    semver_version = semver_from_taskand_version(v_tag)

    desc = raw_data.get("desc") or f"Taskand {organism}/{capability} process"

    # Runtime detection
    if (proc_dir / "bin.mjs").is_file():
        runtime = {"type": "command", "argv": ["node", "bin.mjs"]}
    elif (proc_dir / "bin.py").is_file():
        runtime = {"type": "python", "entry": "bin.py"}
    elif (proc_dir / "run.sh").is_file():
        runtime = {"type": "command", "argv": ["./run.sh"]}
    else:
        runtime = {"type": "command", "argv": ["node", "bin.mjs"]}

    resources = ["proc.yaml"]
    if (proc_dir / "test.mjs").is_file():
        resources.append("test.mjs")

    credentials = raw_data.get("credentials", [])
    if isinstance(credentials, str):
        cleaned = credentials.strip().strip("[]")
        credentials = [c.strip().strip("'").strip('"') for c in cleaned.split(",") if c.strip()]

    host_tools = []
    if runtime["type"] == "command" and runtime.get("argv"):
        first = runtime["argv"][0]
        if not first.startswith("./") and not (proc_dir / first).is_file():
            host_tools.append(first)

    manifest: dict[str, Any] = {
        "paxlet": "0.1",
        "identity": {
            "urn": f"urn:paxlet:taskand:{organism}:{capability}",
            "name": f"{organism}-{capability}",
            "version": semver_version,
        },
        "bindings": [uri] if uri else [],
        "actions": {
            "run": {
                "description": desc,
                "runtime": runtime,
                "input": {"type": "object"},
                "output": {"type": "object"},
            }
        },
        "resources": resources,
        "permissions": {
            "filesystem": {"read": ["."], "write": ["."]},
            "network": ["*"] if organism in {"admin", "alert", "browser", "chat", "web", "cluster", "mcp"} else [],
            "secrets": [str(c) for c in credentials] if credentials else [],
            "host_tools": host_tools,
        },
        "provenance": {
            "source": "taskand",
            "uri": uri,
            "origin": raw_data.get("origin", "evolved"),
        },
        "metadata": {
            "taskand": {
                "organism": organism,
                "capability": capability,
                "kind": raw_data.get("kind", "task"),
                "origin": raw_data.get("origin", "evolved"),
                "supersedes": raw_data.get("supersedes"),
            }
        },
    }

    val = validate_manifest(proc_dir, manifest, check_files=proc_dir.exists())

    if write and val.ok:
        target = Path(output_file).resolve() if output_file else proc_dir / "paxlet.json"
        target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return manifest, val.ok, val.errors


def adapt_directory(
    root_dir: Path | str,
    write: bool = True,
) -> list[tuple[Path, dict[str, Any], bool, list[str]]]:
    """Find and adapt all proc.yaml files in a directory tree."""
    root = Path(root_dir).resolve()
    results = []
    for proc_yaml in sorted(root.rglob("proc.yaml")):
        manifest, ok, errors = adapt_proc_yaml(proc_yaml, write=write)
        results.append((proc_yaml, manifest, ok, errors))
    return results


def export_proc_yaml(proc_yaml_path: Path | str, destination: Path | str) -> tuple[dict[str, Any], bool, list[str]]:
    """Adapt a copy, preserving the source Taskand package and its registered hash.

    The destination is new and caller-owned. No registry entry, activation or grant
    is created. Symlinks are copied as links and rejected by manifest validation.
    """
    source, destination = Path(proc_yaml_path).resolve(), Path(destination).resolve()
    if source.name != "proc.yaml" or not source.is_file():
        raise ValueError("export source must be a proc.yaml file")
    if destination == source.parent or source.parent in destination.parents:
        raise ValueError("export destination must be outside the source package")
    if destination.exists():
        raise ValueError("export destination must not exist")
    shutil.copytree(source.parent, destination, symlinks=True)
    try:
        result = adapt_proc_yaml(destination / "proc.yaml", write=True)
        if not result[1]:
            shutil.rmtree(destination)
        return result
    except Exception:
        shutil.rmtree(destination)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Paxlet manifests from Taskand proc.yaml files")
    parser.add_argument("path", help="Path to proc.yaml or directory containing proc.yaml files")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing paxlet.json")
    parser.add_argument("--output-dir", type=Path, help="export copies to a new directory; preserve Taskand package hashes")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args(argv)

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: path not found: {target}", file=sys.stderr)
        return 1

    if not args.dry_run and args.output_dir is None:
        parser.error("writing requires --output-dir; in-place conversion changes Taskand package hashes")

    if target.is_file() and target.name == "proc.yaml":
        manifest, ok, errors = (adapt_proc_yaml(target, write=False) if args.dry_run else
                                export_proc_yaml(target, args.output_dir))
        if args.json:
            print(json.dumps({"file": str(target), "ok": ok, "errors": errors, "manifest": manifest}, indent=2))
        else:
            status = "✓ VALID" if ok else f"✗ ERRORS: {errors}"
            print(f"{status}  {manifest['identity']['urn']} @ {manifest['identity']['version']}")
        return 0 if ok else 1

    # Directory
    if args.dry_run:
        results = adapt_directory(target, write=False)
    else:
        if args.output_dir.exists() or args.output_dir.resolve() == target or target in args.output_dir.resolve().parents:
            parser.error("output directory must be new and outside the source tree")
        results = []
        for proc_yaml in sorted(target.rglob("proc.yaml")):
            destination = args.output_dir / proc_yaml.parent.relative_to(target)
            manifest, ok, errors = export_proc_yaml(proc_yaml, destination)
            results.append((proc_yaml, manifest, ok, errors))
    success = sum(1 for _, _, ok, _ in results if ok)
    total = len(results)

    if args.json:
        summary = [
            {"proc_yaml": str(p), "urn": m["identity"]["urn"], "version": m["identity"]["version"], "ok": ok, "errors": errs}
            for p, m, ok, errs in results
        ]
        print(json.dumps({"total": total, "valid": success, "items": summary}, indent=2))
    else:
        for p, m, ok, errs in results:
            rel = p.relative_to(target).as_posix()
            status = "✓" if ok else "✗"
            print(f"{status} {m['identity']['urn']} @ {m['identity']['version']} ({rel})")
            if not ok:
                for err in errs:
                    print(f"    - {err}")
        print(f"\nAdapted Taskand processes: {success}/{total} valid Paxlets.")

    return 0 if success == total else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
