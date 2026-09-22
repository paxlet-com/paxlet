from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from paxlet.errors import ManifestError, RuntimeError
from paxlet.manifest import (
    load_manifest,
    package_digest,
    safe_path,
    validate_manifest,
)
from paxlet.packing import pack
from paxlet.runtime import run_action

ROOT = Path(__file__).resolve().parents[1]


class P0SecurityTests(unittest.TestCase):
    def test_package_closure_command_argv(self):
        """P0 #1: Modifying an executable file referenced in argv MUST change the package_digest."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            script = pkg / "run.sh"
            script.write_text("#!/bin/sh\necho '{\"ok\":true}'\n")
            script.chmod(0o755)

            manifest = {
                "paxlet": "0.1",
                "identity": {
                    "urn": "urn:paxlet:test:command-closure",
                    "name": "command-closure",
                    "version": "1.0.0",
                },
                "actions": {
                    "run": {
                        "runtime": {
                            "type": "command",
                            "argv": ["./run.sh"],
                        }
                    }
                },
            }
            (pkg / "paxlet.json").write_text(json.dumps(manifest, indent=2))

            val = validate_manifest(pkg, manifest)
            self.assertTrue(val.ok, f"Validation errors: {val.errors}")

            digest1 = package_digest(pkg, manifest)

            # Modify run.sh
            time.sleep(0.01)
            script.write_text("#!/bin/sh\necho '{\"ok\":false,\"tampered\":true}'\n")

            digest2 = package_digest(pkg, manifest)
            self.assertNotEqual(
                digest1,
                digest2,
                "Package closure failed: modifying run.sh did not change package_digest!",
            )

    def test_symlinks_rejected(self):
        """P0 #2: Symlinks inside a Paxlet package must be strictly rejected."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            real_file = pkg / "real.py"
            real_file.write_text("print('{}')\n")

            symlink_file = pkg / "link.py"
            symlink_file.symlink_to(real_file)

            manifest = {
                "paxlet": "0.1",
                "identity": {
                    "urn": "urn:paxlet:test:symlink-reject",
                    "name": "symlink-reject",
                    "version": "1.0.0",
                },
                "actions": {
                    "run": {
                        "runtime": {
                            "type": "python",
                            "entry": "link.py",
                        }
                    }
                },
            }
            (pkg / "paxlet.json").write_text(json.dumps(manifest, indent=2))

            # validate_manifest must reject symlinks
            val = validate_manifest(pkg, manifest)
            self.assertFalse(val.ok)
            self.assertTrue(any("symlinks are not permitted" in err for err in val.errors))

            # safe_path must reject symlinks
            with self.assertRaises(ManifestError):
                safe_path(pkg, "link.py")

            # pack must reject symlinks
            with self.assertRaises(ManifestError):
                pack(pkg, pkg / "out.paxlet.zip")

    def test_receipt_privacy_secrets(self):
        """P0 #3: Secret values MUST NOT appear in receipts when secrets are granted."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            script = pkg / "worker.py"
            script.write_text(
                "import os, json, sys\n"
                "raw = json.load(sys.stdin)\n"
                "token = os.environ.get('API_SECRET', '')\n"
                "print(json.dumps({'status': 'ok', 'secret': token}))\n"
            )

            manifest = {
                "paxlet": "0.1",
                "identity": {
                    "urn": "urn:paxlet:test:secret-privacy",
                    "name": "secret-privacy",
                    "version": "1.0.0",
                },
                "permissions": {
                    "secrets": ["API_SECRET"],
                },
                "actions": {
                    "run": {
                        "runtime": {
                            "type": "python",
                            "entry": "worker.py",
                        }
                    }
                },
            }
            (pkg / "paxlet.json").write_text(json.dumps(manifest, indent=2))

            secret_value = "SUPER_SECRET_TOKEN_XYZ_123"
            os.environ["API_SECRET"] = secret_value
            try:
                output, receipt, receipt_path = run_action(
                    pkg,
                    "run",
                    {"query": "data"},
                    allow_secrets=["API_SECRET"],
                    write_receipts=True,
                    include_raw_output=True,  # Even if requested!
                )
                # Output returned to caller contains the result
                self.assertEqual(output["secret"], secret_value)

                # BUT receipt MUST NOT leak the secret
                receipt_str = json.dumps(receipt)
                self.assertNotIn(
                    secret_value,
                    receipt_str,
                    "Receipt leaked secret value in in-memory receipt!",
                )
                self.assertNotIn("output", receipt)
                self.assertIsNotNone(receipt["output_digest"])

                # Check on-disk receipt
                self.assertIsNotNone(receipt_path)
                disk_content = receipt_path.read_text(encoding="utf-8")
                self.assertNotIn(
                    secret_value,
                    disk_content,
                    "Receipt leaked secret value in on-disk receipt file!",
                )
            finally:
                del os.environ["API_SECRET"]

    def test_execution_limits_timeout(self):
        """P0 #4: Action execution exceeding timeout is terminated with timeout receipt."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            script = pkg / "hang.py"
            script.write_text("import time\ntime.sleep(10)\n")

            manifest = {
                "paxlet": "0.1",
                "identity": {
                    "urn": "urn:paxlet:test:timeout",
                    "name": "timeout",
                    "version": "1.0.0",
                },
                "actions": {
                    "run": {
                        "runtime": {
                            "type": "python",
                            "entry": "hang.py",
                        },
                        "timeout_seconds": 1,
                    }
                },
            }
            (pkg / "paxlet.json").write_text(json.dumps(manifest, indent=2))

            start_t = time.time()
            with self.assertRaises(RuntimeError) as cm:
                run_action(pkg, "run", {}, write_receipts=True)
            elapsed = time.time() - start_t

            self.assertLess(elapsed, 4.0, "Action did not terminate promptly on timeout!")
            self.assertIn("timed out after 1s", str(cm.exception))

    def test_schema_convergence(self):
        """P0 #5: Schema and validator reject empty actions without resources."""
        manifest = {
            "paxlet": "0.1",
            "identity": {
                "urn": "urn:paxlet:test:empty-actions",
                "name": "empty-actions",
                "version": "1.0.0",
            },
            "actions": {},
        }
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            (pkg / "paxlet.json").write_text(json.dumps(manifest))
            val = validate_manifest(pkg, manifest, check_files=False)
            self.assertFalse(val.ok)
            self.assertTrue(any("must contain at least one action or resource" in e for e in val.errors))

    def test_deterministic_archive(self):
        """P0 #6: pack() must produce bit-for-bit identical archives across repeated runs."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "pkg"
            pkg.mkdir()
            (pkg / "paxlet.json").write_text(json.dumps({
                "paxlet": "0.1",
                "identity": {"urn": "urn:paxlet:test:deterministic", "name": "deterministic", "version": "1.0.0"},
                "resources": ["data.txt"],
            }))
            (pkg / "data.txt").write_text("Hello Determinism!\n")

            out1 = Path(td) / "archive1.zip"
            out2 = Path(td) / "archive2.zip"

            pack(pkg, out1)
            time.sleep(0.05)
            pack(pkg, out2)

            bytes1 = out1.read_bytes()
            bytes2 = out2.read_bytes()
            self.assertEqual(hashlib.sha256(bytes1).hexdigest(), hashlib.sha256(bytes2).hexdigest())

            # Check that zip metadata uses normalized timestamp (2026, 1, 1, 0, 0, 0)
            with zipfile.ZipFile(out1, "r") as zf:
                for info in zf.infolist():
                    self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
