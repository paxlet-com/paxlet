from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import RuntimeError
from .manifest import load_manifest, package_digest, validate_manifest
from .receipt import new_receipt, utc_now, write_receipt
from .schema import validate_value

SAFE_ENV_KEYS = ["PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP", "SystemRoot", "WINDIR"]


def _environment(manifest: dict[str, Any], package_dir: Path, action: str, allow_secrets: list[str]) -> tuple[dict[str, str], list[str]]:
    env = {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}
    declared = set(manifest.get("permissions", {}).get("secrets", []))
    granted: list[str] = []
    for name in allow_secrets:
        if name not in declared:
            raise RuntimeError(f"secret {name!r} is not declared by the Paxlet")
        if name not in os.environ:
            raise RuntimeError(f"secret {name!r} is not present in the current environment")
        env[name] = os.environ[name]
        granted.append(name)
    identity = manifest["identity"]
    env.update({
        "PAXLET_URN": identity["urn"],
        "PAXLET_VERSION": identity["version"],
        "PAXLET_ACTION": action,
        "PAXLET_ROOT": str(package_dir),
    })
    return env, granted


def run_action(path: str | Path, action_name: str, payload: Any, *, allow_secrets: list[str] | None = None, write_receipts: bool = True) -> tuple[Any, dict[str, Any], Path | None]:
    manifest_file, manifest = load_manifest(path)
    package_dir = manifest_file.parent
    result = validate_manifest(package_dir, manifest)
    if not result.ok:
        raise RuntimeError("invalid Paxlet: " + "; ".join(result.errors))

    action = manifest.get("actions", {}).get(action_name)
    if not isinstance(action, dict):
        raise RuntimeError(f"action not found: {action_name}")
    validate_value(payload, action.get("input"), "input")

    runtime = action["runtime"]
    if runtime["type"] == "python":
        command = [sys.executable, runtime["entry"]]
    else:
        command = runtime["argv"]

    env, granted = _environment(manifest, package_dir, action_name, allow_secrets or [])
    started = utc_now()
    completed = subprocess.run(
        command,
        cwd=package_dir,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    finished = utc_now()

    if completed.returncode != 0:
        failure = {
            "error": "action_failed",
            "message": completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}",
        }
        receipt = new_receipt(
            manifest=manifest,
            package_digest=package_digest(package_dir, manifest),
            action=action_name,
            payload=payload,
            started=started,
            finished=finished,
            exit_code=completed.returncode,
            output=failure,
            secret_names=granted,
        )
        receipt_path = write_receipt(package_dir, receipt) if write_receipts else None
        raise RuntimeError(f"action failed ({completed.returncode}): {failure['message']}; receipt={receipt_path}")

    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"action must write exactly one JSON value to stdout; got: {completed.stdout[:200]!r}") from exc
    validate_value(output, action.get("output"), "output")

    receipt = new_receipt(
        manifest=manifest,
        package_digest=package_digest(package_dir, manifest),
        action=action_name,
        payload=payload,
        started=started,
        finished=finished,
        exit_code=0,
        output=output,
        secret_names=granted,
    )
    receipt_path = write_receipt(package_dir, receipt) if write_receipts else None
    return output, receipt, receipt_path
