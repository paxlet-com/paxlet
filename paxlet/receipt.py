from __future__ import annotations

import hashlib
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import canonical_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def value_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def resolve_node_id() -> str:
    """Resolve a cryptographic or persistent URN-based Node identity.

    Precedence:
    1. PAXLET_NODE_ID environment variable (e.g. 'urn:paxlet:node:xyz').
    2. ~/.paxlet/node_id file.
    3. Host machine ID (/etc/machine-id) hashed to urn:paxlet:node:<sha256[:16]>.
    4. Deterministic hash of hostname -> urn:paxlet:node:<sha256[:16]>.
    """
    env_node = os.environ.get("PAXLET_NODE_ID", "").strip()
    if env_node:
        return env_node

    home_dir = Path(os.environ.get("PAXLET_HOME", Path.home() / ".paxlet"))
    node_file = home_dir / "node_id"
    if node_file.is_file():
        try:
            content = node_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        except OSError:
            pass

    for mid_path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        if mid_path.is_file():
            try:
                mid = mid_path.read_text(encoding="utf-8").strip()
                if mid:
                    h = hashlib.sha256(mid.encode("utf-8")).hexdigest()[:16]
                    return f"urn:paxlet:node:{h}"
            except OSError:
                pass

    h = hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()[:16]
    return f"urn:paxlet:node:{h}"


def new_receipt(
    *,
    manifest: dict[str, Any],
    package_digest: str,
    action: str,
    payload: Any,
    started: str,
    finished: str,
    exit_code: int,
    output: Any,
    secret_names: list[str],
    include_raw_output: bool = False,
    artifact_refs: list[str] | None = None,
    node: str | None = None,
    parent_receipt: str | None = None,
    dependencies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identity = manifest["identity"]
    receipt: dict[str, Any] = {
        "receipt": "paxlet/0.1",
        "identity": {"urn": identity["urn"], "version": identity["version"]},
        "package_digest": package_digest,
        "action": action,
        "input_digest": value_digest(payload),
        "output_digest": value_digest(output) if exit_code == 0 else None,
        "runtime": "paxlet-python-reference/0.1.0",
        "node": node or resolve_node_id(),
        "started_at": started,
        "finished_at": finished,
        "exit_code": exit_code,
        "granted_secret_names": sorted(secret_names),
        "artifact_refs": sorted(artifact_refs or []),
    }
    if parent_receipt:
        receipt["parent_receipt"] = parent_receipt
    if dependencies:
        receipt["dependencies"] = dependencies
    # Secret values MUST NOT appear in receipts.
    # Raw output is omitted by default; if explicitly opted-in and no secrets were granted, it may be recorded.
    if include_raw_output and not secret_names:
        receipt["output"] = output
    return receipt


def write_receipt(package_dir: Path, receipt: dict[str, Any]) -> Path:
    directory = package_dir / ".paxlet" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    safe_time = receipt["finished_at"].replace(":", "-").replace(".", "-")
    path = directory / f"{safe_time}-{receipt['action']}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
