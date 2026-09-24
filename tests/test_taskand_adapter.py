from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from integrations.taskand.adapt import adapt_directory, adapt_proc_yaml, export_proc_yaml, parse_taskand_uri, semver_from_taskand_version
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

    def test_rejects_noncanonical_or_missing_process_identity(self):
        for uri in ["", "proc://other.dev/dev/chat/v1", "proc://taskand.dev/dev/chat",
                    "proc://taskand.dev/dev/chat/v1#run", "proc://taskand.dev/dev/%2F/v1"]:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                parse_taskand_uri(uri)

    @unittest.skipUnless(shutil.which("node"), "Node is required for Taskand process execution")
    def test_export_preserves_source_and_resolves_process_alias(self):
        from paxlet.manifest import package_digest
        from paxlet.resolver import resolve_package
        from paxlet.runtime import run_action
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            source.mkdir()
            uri = "proc://taskand.dev/dev/chat/v1"
            (source / "proc.yaml").write_text(f"uri: {uri}\norganism: dev\ncapability: descriptive-label\n")
            (source / "bin.mjs").write_text("import {message} from './helper.mjs'; console.log(JSON.stringify({message}));\n")
            (source / "helper.mjs").write_text("export const message = 'hello';\n")
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            destination = root / "export"
            manifest, ok, errors = export_proc_yaml(source / "proc.yaml", destination)
            self.assertTrue(ok, errors)
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})
            self.assertEqual(manifest["identity"]["urn"], "urn:paxlet:taskand:dev:chat")
            digest = package_digest(destination)
            registry = root / "registry.json"
            registry.write_text(json.dumps({"registry": "paxlet/0.1", "aliases": {uri: manifest["identity"]["urn"]},
                "entries": {manifest["identity"]["urn"]: [{"uri": destination.as_uri(), "version": "1.0.0", "digest": digest}]}}))
            selected = resolve_package(uri, registry, action="run")
            output, receipt, _ = run_action(selected.path, selected.action, {}, expected_digest=selected.digest, write_receipts=False)
            self.assertEqual(output, {"message": "hello"})
            self.assertEqual(receipt["package_digest"], digest)
            with self.assertRaises(ValueError):
                export_proc_yaml(source / "proc.yaml", destination)
            with self.assertRaises(ValueError):
                export_proc_yaml(source / "proc.yaml", source / "nested")


    def test_real_taskand_shell_export_store_and_execution_copy(self):
        import subprocess
        import sys
        taskand = os.environ.get("TASKAND_ROOT")
        if not taskand:
            self.skipTest("set TASKAND_ROOT to exercise the real Taskand shell consumer")
        script = r'''
import json, sys, tempfile
from pathlib import Path
import paxlet
assert Path(paxlet.__file__).resolve().is_relative_to(Path(sys.argv[1]))
from app.shell_workflow import export_package, run_package
from paxlet.store import put_package, list_packages, materialize_package
from paxlet.manifest import package_digest
from unittest.mock import patch
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    plan = {"schema_version":"0.1", "name":"store-roundtrip", "steps":[
        {"id":"hello", "kind":"generate", "language":"python", "code":"print('Witaj Taskand!')\n"}]}
    exported = export_package(plan, root / 'export', urn='urn:paxlet:taskand:store-test', permissions={})
    with patch.dict('os.environ', {'PAXLET_STORE_DIR':str(root / 'store')}):
        digest, archive, installed = put_package(root / 'export', expected_digest=exported['digest'])
        record = list_packages()[0]
        assert record['digest'] == digest and 'run' in record['actions']
        workspace = materialize_package(digest, root / 'execution')
        result = run_package(workspace, expected_digest=digest)
        assert result['output']['stdout'] == 'Witaj Taskand!\n', result
        assert result['receipt']['package_digest'] == digest
        assert package_digest(installed) == digest
        assert not (installed / '.paxlet').exists()
        print(json.dumps({'digest':digest, 'output':result['output']}))
'''
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT), taskand, env.get("PYTHONPATH", "")])
        result = subprocess.run([sys.executable, "-c", script, str(ROOT)], env=env,
                                capture_output=True, text=True, timeout=30, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["output"]["stdout"], "Witaj Taskand!\n")

    def test_adapt_all_taskand_generated(self):
        taskand_generated = Path(os.environ.get("TASKAND_ROOT", ROOT.parent / "taskand")) / "generated"
        if not taskand_generated.exists():
            self.skipTest("set TASKAND_ROOT to exercise the local Taskand catalog")
        if taskand_generated.exists():
            results = adapt_directory(taskand_generated, write=False)
            self.assertGreaterEqual(len(results), 24)
            for proc_yaml, manifest, ok, errors in results:
                self.assertTrue(ok, f"Failed on {proc_yaml}: {errors}")


if __name__ == "__main__":
    unittest.main()
