from __future__ import annotations

import argparse
import json
import re
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
    m = re.match(r"^proc://([^/]+)/([^/]+)/([^/]+)/(v\d+(?:\.\d+)*)$", uri.strip())
    if not m:
        parts = uri.replace("proc://", "").strip("/").split("/")
        if len(parts) >= 4:
            return {"host": parts[0], "organism": parts[1], "capability": parts[2], "version": parts[3]}
        elif len(parts) == 3:
            return {"host": parts[0], "organism": parts[1], "capability": parts[2], "version": "v1"}
        return {"host": "taskand.dev", "organism": "task", "capability": "process", "version": "v1"}
    return {
        "host": m.group(1),
        "organism": m.group(2),
        "capability": m.group(3),
        "version": m.group(4),
    }


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

    uri = str(raw_data.get("uri", "")).strip()
    parsed_uri = parse_taskand_uri(uri) if uri else {}

    organism = str(raw_data.get("organism") or parsed_uri.get("organism") or "task").strip()

    # Prefer clean slug from URI or directory path if raw_data capability contains long text/spaces
    uri_cap = parsed_uri.get("capability", "").strip()
    raw_cap = str(raw_data.get("capability") or "").strip()
    if uri_cap and (not raw_cap or " " in raw_cap or len(raw_cap) > 40):
        capability = uri_cap
    elif raw_cap and " " not in raw_cap:
        capability = raw_cap
    else:
        capability = uri_cap or proc_dir.parent.parent.name
    capability = "".join(ch.lower() if ch.isalnum() else "-" for ch in capability).strip("-")
    while "--" in capability:
        capability = capability.replace("--", "-")
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

    if write:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Paxlet manifests from Taskand proc.yaml files")
    parser.add_argument("path", help="Path to proc.yaml or directory containing proc.yaml files")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing paxlet.json")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args(argv)

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: path not found: {target}", file=sys.stderr)
        return 1

    if target.is_file() and target.name == "proc.yaml":
        manifest, ok, errors = adapt_proc_yaml(target, write=not args.dry_run)
        if args.json:
            print(json.dumps({"file": str(target), "ok": ok, "errors": errors, "manifest": manifest}, indent=2))
        else:
            status = "✓ VALID" if ok else f"✗ ERRORS: {errors}"
            print(f"{status}  {manifest['identity']['urn']} @ {manifest['identity']['version']}")
        return 0 if ok else 1

    # Directory
    results = adapt_directory(target, write=not args.dry_run)
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
    raise SystemExit(main())
