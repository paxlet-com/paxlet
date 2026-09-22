from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from integrations.taskand.adapt import adapt_directory, adapt_proc_yaml, parse_taskand_uri, semver_from_taskand_version
from paxlet.manifest import validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class TaskandAdapterTests(unittest.TestCase):
    def test_version_conversion(self):
        self.assertEqual(semver_from_taskand_version("v1"), "1.0.0")
        self.assertEqual(semver_from_taskand_version("v4"), "4.0.0")
        self.assertEqual(semver_from_taskand_version("v2.1"), "2.1.0")
        self.assertEqual(semver_from_taskand_version("3.2.1"), "3.2.1")

    def test_uri_parsing(self):
        parsed = parse_taskand_uri("proc://taskand.dev/admin/network-device-discovery/v4")
        self.assertEqual(parsed["host"], "taskand.dev")
        self.assertEqual(parsed["organism"], "admin")
        self.assertEqual(parsed["capability"], "network-device-discovery")
        self.assertEqual(parsed["version"], "v4")

    def test_adapt_single_proc(self):
        with tempfile.TemporaryDirectory() as td:
            proc_dir = Path(td)
            (proc_dir / "proc.yaml").write_text(
                "uri: proc://taskand.dev/dev/chat/v1\n"
                "organism: dev\n"
                "kind: task\n"
                "origin: evolved\n"
                "desc: Dev chat capability\n"
                "credentials: [TEST_SECRET]\n"
            )
            (proc_dir / "bin.mjs").write_text("#!/usr/bin/env node\nconsole.log('{}');\n")
            (proc_dir / "test.mjs").write_text("console.log('PASS');\n")

            manifest, ok, errors = adapt_proc_yaml(proc_dir / "proc.yaml", write=True)
            self.assertTrue(ok, f"Manifest validation errors: {errors}")
            self.assertEqual(manifest["identity"]["urn"], "urn:paxlet:taskand:dev:chat")
            self.assertEqual(manifest["identity"]["version"], "1.0.0")
            self.assertEqual(manifest["actions"]["run"]["runtime"]["argv"], ["node", "bin.mjs"])
            self.assertIn("TEST_SECRET", manifest["permissions"]["secrets"])
            self.assertTrue((proc_dir / "paxlet.json").exists())

            # Check that paxlet.json validates with validate_manifest
            val = validate_manifest(proc_dir, manifest)
            self.assertTrue(val.ok)

    def test_adapt_all_taskand_generated(self):
        taskand_generated = ROOT.parent / "taskand" / "generated"
        if taskand_generated.exists():
            results = adapt_directory(taskand_generated, write=False)
            self.assertGreaterEqual(len(results), 24)
            for proc_yaml, manifest, ok, errors in results:
                self.assertTrue(ok, f"Failed on {proc_yaml}: {errors}")


if __name__ == "__main__":
    unittest.main()
