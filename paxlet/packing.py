from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .errors import ManifestError
from .manifest import collect_package_files, load_manifest, package_digest, validate_manifest


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
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in collect_package_files(root, manifest):
            zf.write(file, file.relative_to(root).as_posix())
        info = zipfile.ZipInfo("PAXLET-METADATA.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return out
