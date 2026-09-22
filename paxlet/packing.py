from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .errors import ManifestError
from .manifest import collect_package_files, load_manifest, package_digest, validate_manifest


DETERMINISTIC_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def pack(path: str | Path, output: str | Path) -> Path:
    manifest_file, manifest = load_manifest(path)
    root = manifest_file.parent
    result = validate_manifest(root, manifest)
    if not result.ok:
        raise ManifestError("cannot pack invalid Paxlet: " + "; ".join(result.errors))
    out = Path(output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "format": "paxlet-archive/0.1",
        "identity": manifest["identity"],
        "package_digest": package_digest(root, manifest),
    }

    files = collect_package_files(root, manifest)

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            rel_path = file.relative_to(root).as_posix()
            data = file.read_bytes()
            is_exec = bool(file.stat().st_mode & 0o111)
            perm = 0o755 if is_exec else 0o644

            info = zipfile.ZipInfo(rel_path, date_time=DETERMINISTIC_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # UNIX
            info.external_attr = (0o100000 | perm) << 16
            zf.writestr(info, data)

        meta_info = zipfile.ZipInfo("PAXLET-METADATA.json", date_time=DETERMINISTIC_TIMESTAMP)
        meta_info.compress_type = zipfile.ZIP_DEFLATED
        meta_info.create_system = 3  # UNIX
        meta_info.external_attr = (0o100000 | 0o644) << 16
        zf.writestr(meta_info, json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    return out
