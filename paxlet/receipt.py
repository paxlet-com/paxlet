from __future__ import annotations

import hashlib
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import canonical_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def value_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def new_receipt(*, manifest: dict[str, Any], package_digest: str, action: str, payload: Any, started: str, finished: str, exit_code: int, output: Any, secret_names: list[str]) -> dict[str, Any]:
    identity = manifest["identity"]
    return {
        "receipt": "paxlet/0.1",
        "identity": {"urn": identity["urn"], "version": identity["version"]},
        "package_digest": package_digest,
        "action": action,
        "input_digest": value_digest(payload),
        "output_digest": value_digest(output) if exit_code == 0 else None,
        "runtime": "paxlet-python-reference/0.1.0",
        "node": socket.gethostname(),
        "started_at": started,
        "finished_at": finished,
        "exit_code": exit_code,
        "granted_secret_names": sorted(secret_names),
        "output": output,
    }


def write_receipt(package_dir: Path, receipt: dict[str, Any]) -> Path:
    directory = package_dir / ".paxlet" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    safe_time = receipt["finished_at"].replace(":", "-").replace(".", "-")
    path = directory / f"{safe_time}-{receipt['action']}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
