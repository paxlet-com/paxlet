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

    def test_host_tool_declaration_enforcement(self):
        """P0 #7: Host executables in command runtime must be explicitly declared."""
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td)
            script = pkg / "bin.js"
            script.write_text("console.log('{}');\n")

            manifest_undeclared = {
                "paxlet": "0.1",
                "identity": {"urn": "urn:paxlet:test:host-tools", "name": "host-tools", "version": "1.0.0"},
                "actions": {
                    "run": {
                        "runtime": {"type": "command", "argv": ["node", "bin.js"]},
                    }
                },
            }
            (pkg / "paxlet.json").write_text(json.dumps(manifest_undeclared, indent=2))

            # Fails validation because 'node' is not declared
            val = validate_manifest(pkg, manifest_undeclared)
            self.assertFalse(val.ok)
            self.assertTrue(any("undeclared host executable 'node'" in e for e in val.errors))

            # Declaring in permissions.host_tools passes
            manifest_declared = dict(manifest_undeclared)
            manifest_declared["permissions"] = {"host_tools": ["node"]}
            (pkg / "paxlet.json").write_text(json.dumps(manifest_declared, indent=2))
            val2 = validate_manifest(pkg, manifest_declared)
            self.assertTrue(val2.ok, f"Expected valid, got: {val2.errors}")

    def test_resolver_digest_verification(self):
        """P1: Resolver must detect and reject digest mismatch."""
        from paxlet.resolver import resolve_to_path
        from paxlet.errors import ResolutionError

        with tempfile.TemporaryDirectory() as td:
            reg_dir = Path(td)
            pkg = reg_dir / "pkg"
            pkg.mkdir()
            (pkg / "paxlet.json").write_text(json.dumps({
                "paxlet": "0.1",
                "identity": {"urn": "urn:paxlet:test:digest-verify", "name": "digest-verify", "version": "1.0.0"},
                "resources": ["hello.txt"],
            }))
            (pkg / "hello.txt").write_text("Hello!\n")
            actual_digest = package_digest(pkg)

            # Registry with wrong digest
            reg_file = reg_dir / "registry.json"
            reg_file.write_text(json.dumps({
                "registry": "paxlet/0.1",
                "entries": {
                    "urn:paxlet:test:digest-verify": [
                        {
                            "version": "1.0.0",
                            "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                            "uri": f"file:{pkg}",
                        }
                    ]
                }
            }))

            with self.assertRaises(ResolutionError) as cm:
                resolve_to_path("urn:paxlet:test:digest-verify", registry_path=reg_file, verify_digest=True)
            self.assertIn("package digest mismatch", str(cm.exception))

            # Registry with correct digest succeeds
            reg_file.write_text(json.dumps({
                "registry": "paxlet/0.1",
                "entries": {
                    "urn:paxlet:test:digest-verify": [
                        {
                            "version": "1.0.0",
                            "digest": actual_digest,
                            "uri": f"file:{pkg}",
                        }
                    ]
                }
            }))
            resolved_path = resolve_to_path("urn:paxlet:test:digest-verify", registry_path=reg_file, verify_digest=True)
            self.assertEqual(resolved_path.resolve(), pkg.resolve())

    def test_node_identity_urn(self):
        """P1: Node identity must use a URN format instead of raw ephemeral hostname."""
        from paxlet.receipt import new_receipt, resolve_node_id

        # Derives urn:paxlet:node:...
        node_id = resolve_node_id()
        self.assertTrue(node_id.startswith("urn:paxlet:node:") or node_id.startswith("node:"))

        # Custom environment override
        os.environ["PAXLET_NODE_ID"] = "urn:paxlet:node:custom-worker-42"
        try:
            self.assertEqual(resolve_node_id(), "urn:paxlet:node:custom-worker-42")
            receipt = new_receipt(
                manifest={"identity": {"urn": "urn:paxlet:test:node", "version": "1.0.0"}},
                package_digest="sha256:abc",
                action="test",
                payload={},
                started="2026-01-01T00:00:00Z",
                finished="2026-01-01T00:00:01Z",
                exit_code=0,
                output={},
                secret_names=[],
            )
            self.assertEqual(receipt["node"], "urn:paxlet:node:custom-worker-42")
        finally:
            del os.environ["PAXLET_NODE_ID"]

    def test_content_addressed_store(self):
        """P1: Content-addressed store puts, gets, and verifies packages."""
        from paxlet.store import put_package, get_package, has_package, list_packages

        with tempfile.TemporaryDirectory() as td:
            os.environ["PAXLET_STORE_DIR"] = str(Path(td) / "store")
            try:
                pkg = Path(td) / "sample"
                pkg.mkdir()
                (pkg / "paxlet.json").write_text(json.dumps({
                    "paxlet": "0.1",
                    "identity": {"urn": "urn:paxlet:test:cas", "name": "cas-test", "version": "1.0.0"},
                    "resources": ["file.txt"],
                }))
                (pkg / "file.txt").write_text("CAS Content\n")

                digest, archive, unpacked = put_package(pkg)
                self.assertTrue(has_package(digest))
                self.assertTrue(archive.exists())
                self.assertTrue(unpacked.exists())

                # Get by digest
                retrieved = get_package(digest)
                self.assertIsNotNone(retrieved)
                self.assertEqual(retrieved.resolve(), unpacked.resolve())

                # Get by URN
                by_urn = get_package("urn:paxlet:test:cas")
                self.assertIsNotNone(by_urn)

                # List packages
                records = list_packages()
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["urn"], "urn:paxlet:test:cas")
                self.assertEqual(records[0]["digest"], digest)
            finally:
                del os.environ["PAXLET_STORE_DIR"]


if __name__ == "__main__":
    unittest.main()
