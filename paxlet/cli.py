from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .errors import PaxletError
from .manifest import load_manifest, package_digest, validate_manifest
from .packing import pack as pack_paxlet
from .resolver import resolve, resolve_to_path
from .runtime import run_action


def _target(value: str, registry: str | None) -> Path:
    if value.startswith("urn:paxlet:"):
        from .store import get_package
        stored = get_package(value)
        if stored and stored.is_dir():
            return stored
        return resolve_to_path(value, registry)
    return Path(value)


def _json(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))



def command_init(args) -> int:
    target = Path(args.directory).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not args.force:
        raise PaxletError(f"directory is not empty: {target}; use --force to add starter files")
    target.mkdir(parents=True, exist_ok=True)
    name = args.name or target.name
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    urn = args.urn or f"urn:paxlet:local:{slug}"
    manifest = {
        "paxlet": "0.1",
        "identity": {"urn": urn, "name": name, "version": "0.1.0"},
        "bindings": [],
        "actions": {
            "hello": {
                "description": "Your first Paxlet action.",
                "runtime": {"type": "python", "entry": "hello.py"},
                "input": {"type": "object", "properties": {"name": {"type": "string"}}},
                "output": {"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}}}
            }
        },
        "resources": [],
        "requires": [],
        "permissions": {"filesystem": {"read": [], "write": []}, "network": [], "secrets": []},
        "provenance": {"created_by": "paxlet init"}
    }
    manifest_file = target / "paxlet.json"
    entry_file = target / "hello.py"
    if not args.force and (manifest_file.exists() or entry_file.exists()):
        raise PaxletError("starter files already exist; use --force to overwrite them")
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    entry_file.write_text(
        'import json, sys\n'
        'payload = json.load(sys.stdin)\n'
        'name = payload.get("name", "world")\n'
        'print(json.dumps({"message": f"Hello, {name}!"}))\n',
        encoding="utf-8",
    )
    print(target)
    print(f"next: paxlet run {target} hello --input '{{\"name\":\"Ada\"}}'")
    return 0

def command_verify(args) -> int:
    path = _target(args.target, args.registry)
    manifest_file, manifest = load_manifest(path)
    result = validate_manifest(manifest_file.parent, manifest)
    payload = {"ok": result.ok, "errors": result.errors, "warnings": result.warnings}
    if result.ok:
        payload["identity"] = manifest["identity"]
        payload["package_digest"] = package_digest(manifest_file.parent, manifest)
    if args.json:
        _json(payload)
    else:
        print("✓ valid Paxlet" if result.ok else "✗ invalid Paxlet")
        for warning in result.warnings:
            print(f"! {warning}")
        for error in result.errors:
            print(f"- {error}")
        if result.ok:
            print(f"  {manifest['identity']['urn']} @ {manifest['identity']['version']}")
            print(f"  {payload['package_digest']}")
    return 0 if result.ok else 1


def command_inspect(args) -> int:
    path = _target(args.target, args.registry)
    manifest_file, manifest = load_manifest(path)
    result = validate_manifest(manifest_file.parent, manifest)
    payload = {
        "valid": result.ok,
        "identity": manifest.get("identity"),
        "bindings": manifest.get("bindings", []),
        "actions": sorted(manifest.get("actions", {}).keys()),
        "resources": manifest.get("resources", []),
        "requires": manifest.get("requires", []),
        "permissions": manifest.get("permissions", {}),
        "package_digest": package_digest(manifest_file.parent, manifest) if result.ok else None,
        "warnings": result.warnings,
        "errors": result.errors,
    }
    _json(payload)
    return 0 if result.ok else 1


def command_run(args) -> int:
    path = _target(args.target, args.registry)
    try:
        payload = json.loads(args.input)
    except json.JSONDecodeError as exc:
        raise PaxletError(f"--input must be valid JSON: {exc}") from exc
    output, receipt, receipt_path = run_action(
        path,
        args.action,
        payload,
        allow_secrets=args.allow_secret,
        write_receipts=not args.no_receipt,
    )
    _json(output)
    if receipt_path:
        print(f"receipt: {receipt_path}", file=sys.stderr)
    if args.show_receipt:
        print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 0


def command_resolve(args) -> int:
    locations = resolve(args.urn, args.registry, version=getattr(args, "urn_version", None))
    _json({"urn": args.urn, "locations": locations})
    return 0


def command_pack(args) -> int:
    output = args.output or (Path(args.target).resolve().name + ".paxlet.zip")
    path = pack_paxlet(_target(args.target, args.registry), output)
    print(path)
    return 0


def command_store_put(args) -> int:
    from .store import put_package
    target = _target(args.target, args.registry)
    digest, archive, unpacked = put_package(target)
    if args.json:
        _json({"digest": digest, "archive": str(archive), "path": str(unpacked)})
    else:
        print(f"✓ stored {digest}")
        print(f"  archive:  {archive}")
        print(f"  unpacked: {unpacked}")
    return 0


def command_store_get(args) -> int:
    from .store import get_package
    p = get_package(args.target)
    if not p:
        raise PaxletError(f"package not found in store: {args.target}")
    print(str(p))
    return 0


def command_store_list(args) -> int:
    from .store import list_packages
    records = list_packages()
    if args.json:
        _json(records)
    else:
        if not records:
            print("Store is empty.")
            return 0
        for r in records:
            print(f"{r.get('urn')}@{r.get('version')} -> {r.get('digest')} ({r.get('path')})")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="paxlet", description="Paxlet Core 0.1 reference CLI")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a minimal runnable Paxlet")
    init.add_argument("directory")
    init.add_argument("--name")
    init.add_argument("--urn")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    verify = sub.add_parser("verify", help="validate a Paxlet manifest and package")
    verify.add_argument("target")
    verify.add_argument("--registry")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=command_verify)

    inspect = sub.add_parser("inspect", help="show the public contract of a Paxlet")
    inspect.add_argument("target")
    inspect.add_argument("--registry")
    inspect.set_defaults(func=command_inspect)

    run = sub.add_parser("run", help="execute one action using JSON stdin/stdout protocol")
    run.add_argument("target")
    run.add_argument("action")
    run.add_argument("--input", default="{}")
    run.add_argument("--registry")
    run.add_argument("--allow-secret", action="append", default=[])
    run.add_argument("--no-receipt", action="store_true")
    run.add_argument("--show-receipt", action="store_true")
    run.set_defaults(func=command_run)

    resolve_cmd = sub.add_parser("resolve", help="resolve a stable Paxlet URN to locations")
    resolve_cmd.add_argument("urn")
    resolve_cmd.add_argument("--registry")
    resolve_cmd.add_argument("--version", dest="urn_version", help="filter by version")
    resolve_cmd.set_defaults(func=command_resolve)

    pack_cmd = sub.add_parser("pack", help="create a portable .paxlet.zip archive")
    pack_cmd.add_argument("target")
    pack_cmd.add_argument("-o", "--output")
    pack_cmd.add_argument("--registry")
    pack_cmd.set_defaults(func=command_pack)

    store_parser = sub.add_parser("store", help="manage content-addressed local store")
    store_sub = store_parser.add_subparsers(dest="store_action", required=True)

    store_put = store_sub.add_parser("put", help="put package into content-addressed store")
    store_put.add_argument("target")
    store_put.add_argument("--registry")
    store_put.add_argument("--json", action="store_true")
    store_put.set_defaults(func=command_store_put)

    store_get = store_sub.add_parser("get", help="get unpacked package path from store by digest or URN")
    store_get.add_argument("target")
    store_get.set_defaults(func=command_store_get)

    store_list = store_sub.add_parser("list", help="list all stored packages")
    store_list.add_argument("--json", action="store_true")
    store_list.set_defaults(func=command_store_list)

    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except PaxletError as exc:
        print(f"paxlet: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
