import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from paxlet.errors import ManifestError
from paxlet.manifest import load_manifest, validate_manifest
from paxlet.packing import pack
from paxlet.resolver import resolve_to_path
from paxlet.runtime import run_action

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_init_creates_runnable_package(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "first"
            created = subprocess.run([sys.executable, "-m", "paxlet.cli", "init", str(target)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            output, _, _ = run_action(target, "hello", {"name": "Ada"}, write_receipts=False)
            self.assertEqual(output["message"], "Hello, Ada!")

    def test_hello_validates(self):
        mf, data = load_manifest(ROOT / "examples/hello")
        self.assertTrue(validate_manifest(mf.parent, data).ok)

    def test_path_escape_rejected(self):
        mf, data = load_manifest(ROOT / "tests/fixtures/invalid-escape")
        result = validate_manifest(mf.parent, data)
        self.assertFalse(result.ok)
        self.assertTrue(any("escapes package root" in e for e in result.errors))

    def test_run_hello_and_receipt(self):
        output, receipt, _ = run_action(ROOT / "examples/hello", "hello", {"name": "Ada"}, write_receipts=False)
        self.assertEqual(output, {"message": "Hello, Ada!"})
        self.assertEqual(receipt["identity"]["urn"], "urn:paxlet:example:hello")
        self.assertTrue(receipt["package_digest"].startswith("sha256:"))

    def test_resolver(self):
        path = resolve_to_path("urn:paxlet:science:fasta-gc", ROOT / "registry/local.json")
        self.assertEqual(path, (ROOT / "examples/science-fasta-gc").resolve())

    def test_pack(self):
        with tempfile.TemporaryDirectory() as td:
            out = pack(ROOT / "examples/hello", Path(td) / "hello.paxlet.zip")
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
