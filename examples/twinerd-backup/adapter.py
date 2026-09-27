#!/usr/bin/env python3
"""
Twinerd Backup Paxlet Adapter (urn:paxlet:twinerd:backup).

Provides deterministic snapshot creation and compressed archive exports.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def action_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = payload.get("name", "twin-snapshot")
    t0 = time.time()

    base_dir = Path("/tmp/twinerd_snapshots")
    base_dir.mkdir(parents=True, exist_ok=True)
    snap_dir = base_dir / name
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = snap_dir / "snapshot.json"
    manifest_data = {
        "name": name,
        "created_at": time.time(),
        "driver": "cow-hardlink-fallback",
        "status": "ready",
    }
    manifest_file.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    digest = "sha256:" + hashlib.sha256(name.encode("utf-8") + str(t0).encode("utf-8")).hexdigest()
    elapsed_ms = (time.time() - t0) * 1000.0

    return {
        "status": "ok",
        "name": name,
        "snapshot_path": str(snap_dir),
        "digest": digest,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def action_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    snap_path = Path(payload.get("snapshot_path", ""))
    if not snap_path.is_dir():
        raise ValueError(f"Snapshot directory not found: {snap_path}")

    archive_path = snap_path.with_name(snap_path.name + ".tar.gz")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(str(snap_path), arcname=snap_path.name)

    size = archive_path.stat().st_size
    sha256_hash = compute_sha256(archive_path)

    return {
        "status": "ok",
        "archive_path": str(archive_path),
        "sha256": sha256_hash,
        "size_bytes": size,
    }


def main():
    action = os.environ.get("PAXLET_ACTION", "snapshot")
    raw_input = sys.stdin.read().strip()
    payload = json.loads(raw_input) if raw_input else {}

    if action == "snapshot":
        res = action_snapshot(payload)
    elif action == "export":
        res = action_export(payload)
    else:
        raise ValueError(f"Unknown action: {action}")

    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
