from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import RuntimeError
from .manifest import load_manifest, package_digest, safe_path, validate_manifest
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


DEFAULT_TIMEOUT_SECONDS = 30
MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_BYTES = 10 * 1024 * 1024


def run_action(
    path: str | Path,
    action_name: str,
    payload: Any,
    *,
    allow_secrets: list[str] | None = None,
    write_receipts: bool = True,
    include_raw_output: bool = False,
    timeout: int | None = None,
) -> tuple[Any, dict[str, Any], Path | None]:
    manifest_file, manifest = load_manifest(path)
    package_dir = manifest_file.parent
    result = validate_manifest(package_dir, manifest)
    if not result.ok:
        raise RuntimeError("invalid Paxlet: " + "; ".join(result.errors))

    action = manifest.get("actions", {}).get(action_name)
    if not isinstance(action, dict):
        raise RuntimeError(f"action not found: {action_name}")
    validate_value(payload, action.get("input"), "input")

    raw_input = json.dumps(payload, ensure_ascii=False)
    input_bytes = raw_input.encode("utf-8")
    if len(input_bytes) > MAX_INPUT_BYTES:
        raise RuntimeError(f"input payload exceeds maximum size ({len(input_bytes)} > {MAX_INPUT_BYTES} bytes)")

    runtime = action["runtime"]
    if runtime["type"] == "python":
        entry_path = safe_path(package_dir, runtime["entry"])
        command = [sys.executable, str(entry_path)]
    else:
        argv = list(runtime["argv"])
        first = argv[0]
        if first.startswith("./") or (not first.startswith("/") and (package_dir / first).is_file()):
            clean_first = first[2:] if first.startswith("./") else first
            first_path = safe_path(package_dir, clean_first)
            argv[0] = str(first_path)
        if len(argv) > 1 and not argv[1].startswith("/"):
            if (package_dir / argv[1]).is_file():
                argv[1] = str(safe_path(package_dir, argv[1]))
        command = argv

    env, granted = _environment(manifest, package_dir, action_name, allow_secrets or [])
    timeout_seconds = timeout or int(action.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

    started = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=package_dir,
            input=raw_input,
            text=True,
            capture_output=True,
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        finished = utc_now()
        failure = {
            "error": "action_timeout",
            "message": f"action timed out after {timeout_seconds}s",
        }
        receipt = new_receipt(
            manifest=manifest,
            package_digest=package_digest(package_dir, manifest),
            action=action_name,
            payload=payload,
            started=started,
            finished=finished,
            exit_code=124,
            output=failure,
            secret_names=granted,
            include_raw_output=include_raw_output,
        )
        receipt_path = write_receipt(package_dir, receipt) if write_receipts else None
        raise RuntimeError(f"action timed out after {timeout_seconds}s; receipt={receipt_path}") from exc

    finished = utc_now()

    if len(completed.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise RuntimeError(f"action stdout exceeded maximum size of {MAX_OUTPUT_BYTES} bytes")
    if len(completed.stderr.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise RuntimeError(f"action stderr exceeded maximum size of {MAX_OUTPUT_BYTES} bytes")

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
            include_raw_output=include_raw_output,
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
        include_raw_output=include_raw_output,
    )
    receipt_path = write_receipt(package_dir, receipt) if write_receipts else None
    return output, receipt, receipt_path
