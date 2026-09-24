from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paxlet.cli import main
from paxlet.errors import ResolutionError, RuntimeError
from paxlet.manifest import package_digest, validate_manifest
from paxlet.references import parse_reference
from paxlet.resolver import load_registry, resolve, resolve_package, resolve_to_path, uri_to_path
from paxlet.runtime import run_action

ROOT = Path(__file__).resolve().parents[1]
URN = "urn:paxlet:example:hello"
ALIAS = "paxlet://example/hello"
ACTION = ALIAS + "/actions/hello"


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "hello"
        shutil.copytree(ROOT / "examples/hello", self.package)
        self.manifest = json.loads((self.package / "paxlet.json").read_text())
        self.manifest["bindings"] = [ALIAS]
        self.save_manifest()
        self.registry = self.root / "registry.json"
        self.data = {"registry": "paxlet/0.1", "aliases": {ALIAS: URN}, "entries": {
            URN: [{"version": "1.0.0", "uri": "file:hello"}]
        }}
        self.save_registry()

    def save_manifest(self):
        (self.package / "paxlet.json").write_text(json.dumps(self.manifest))

    def save_registry(self):
        self.registry.write_text(json.dumps(self.data))

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main([*args, "--registry", str(self.registry)])
        return status, out.getvalue(), err.getvalue()

    def test_urn_and_uri_resolve_to_same_pinned_action(self):
        a = resolve_package(URN, self.registry, action="hello")
        b = resolve_package(ACTION + "?version=1.0.0", self.registry)
        self.assertEqual(a, b)
        self.assertEqual(a.plan(), {"package": URN, "action": "hello", "version": "1.0.0",
                                    "digest": package_digest(self.package)})
        for target, action in [(URN, ["hello"]), (ACTION, [])]:
            status, out, err = self.cli("invoke", target, *action, "--input", '{"name":"Ada"}', "--no-receipt")
            self.assertEqual(status, 0, err)
            self.assertEqual(json.loads(out), {"message": "Hello, Ada!"})

    def test_manifest_claim_does_not_register_alias(self):
        self.data.pop("aliases")
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "not registered"):
            resolve_package(ACTION, self.registry)

    def test_registered_alias_must_be_declared_by_package(self):
        self.manifest["bindings"] = []
        self.save_manifest()
        with self.assertRaisesRegex(ResolutionError, "does not declare"):
            resolve_package(ACTION, self.registry)

    def test_alias_is_not_inferred_from_authority_and_path(self):
        self.manifest["identity"]["urn"] = "urn:paxlet:owner:different-name"
        self.save_manifest()
        self.data["entries"][self.manifest["identity"]["urn"]] = self.data["entries"].pop(URN)
        self.data["aliases"][ALIAS] = self.manifest["identity"]["urn"]
        self.save_registry()
        self.assertEqual(resolve_package(ACTION, self.registry).package, self.manifest["identity"]["urn"])

    def test_conflicting_alias_definitions_are_rejected(self):
        self.registry.write_text('{"registry":"paxlet/0.1","entries":{},"aliases":{'
                                 '"paxlet://example/hello":"urn:paxlet:a",'
                                 '"paxlet://example/hello":"urn:paxlet:b"}}')
        with self.assertRaisesRegex(ResolutionError, "duplicate"):
            load_registry(self.registry)
        self.data["entries"][ALIAS] = self.data["entries"][URN]
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "conflicting alias"):
            load_registry(self.registry)

    def test_uri_profile_rejects_ambiguous_syntax(self):
        suffixes = ["/actions/", "/actions/a/b", "/actions/%2F", "/actions/%23",
                    "/actions/%252F", "/actions/%61", "/actions/..", "#hello", "#",
                    "?", "?version=", "?other=1", "?version=1&version=1", "?version=1&x=2",
                    "?version=%31", "/", "/actions/hello?input=x"]
        values = [ALIAS + suffix for suffix in suffixes] + [
            "paxlet://example/../actions/hello", "paxlet://Example/hello", "paxlet://user@example/hello",
            "paxlet://example:80/hello", "paxlet://example/hel lo", "paxlet://example/he\nllo",
            "paxlet://example/hello\\actions\\hello", "paxlet://example/hello/actions/hello#", ":"]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ResolutionError):
                parse_reference(value)

    def test_binding_validation_rejects_invalid_and_action_addresses(self):
        for value in [":", "not a URI", "https://", "https://host/%xx", ACTION, ALIAS + "?version=1", 2]:
            with self.subTest(value=value):
                self.manifest["bindings"] = [value]
                self.assertFalse(validate_manifest(self.package, self.manifest).ok)
        for value in [ALIAS, "proc://taskand.dev/dev/chat/v1", "https://example.org/package"]:
            self.manifest["bindings"] = [value]
            self.assertTrue(validate_manifest(self.package, self.manifest).ok)

    def test_fallback_skips_transport_and_missing_local_replica(self):
        self.data["entries"][URN][:0] = [
            {"version": "1.0.0", "uri": "https://mirror.example/pkg"},
            {"version": "1.0.0", "uri": "file://remote/pkg"},
            {"version": "1.0.0", "uri": "file:missing"}]
        self.save_registry()
        self.assertEqual(resolve_to_path(URN, self.registry), self.package)

    def test_integrity_failure_does_not_fallback(self):
        mirror = self.root / "mirror"
        shutil.copytree(self.package, mirror)
        self.data["entries"][URN].append({"version": "1.0.0", "uri": mirror.as_uri()})
        self.data["entries"][URN][0]["digest"] = package_digest(self.package)
        (self.package / "hello.py").write_text("print('tampered')")
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "digest mismatch"):
            resolve_to_path(URN, self.registry)

    def test_identity_and_manifest_version_checked_without_digest(self):
        for key, value in [("urn", "urn:paxlet:attacker:hello"), ("version", "2.0.0")]:
            with self.subTest(key=key):
                previous = self.manifest["identity"][key]
                self.manifest["identity"][key] = value
                self.save_manifest()
                with self.assertRaisesRegex(ResolutionError, "identity/version"):
                    resolve_package(URN, self.registry)
                self.manifest["identity"][key] = previous

    def test_conflicting_versions_require_explicit_selection(self):
        self.data["entries"][URN].append({"version": "2.0.0", "uri": "https://mirror.example/v2"})
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "multiple package versions"):
            resolve_package(URN, self.registry)
        self.assertEqual(resolve_package(ACTION + "?version=1.0.0", self.registry).path, self.package)
        with self.assertRaisesRegex(ResolutionError, "conflicting version"):
            resolve_package(ACTION + "?version=1.0.0", self.registry, version="2.0.0")
        with self.assertRaisesRegex(ResolutionError, "conflicting action"):
            resolve_package(ACTION, self.registry, action="other")

    def test_digest_pin_and_conflicting_registry_digests(self):
        digest = package_digest(self.package)
        self.assertEqual(resolve_package(ACTION, self.registry, digest=digest).digest, digest)
        with self.assertRaisesRegex(ResolutionError, "digest mismatch"):
            resolve_package(ACTION, self.registry, digest="sha256:" + "0" * 64)
        self.data["entries"][URN][0]["digest"] = digest
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "conflicting package digests"):
            resolve_package(ACTION, self.registry, digest="sha256:" + "0" * 64)
        self.data["entries"][URN][0]["digest"] = "invalid"
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "digest must"):
            resolve_package(ACTION, self.registry)

    def test_unpinned_local_mirrors_cannot_disagree(self):
        mirror = self.root / "mirror"
        shutil.copytree(self.package, mirror)
        (mirror / "extra.txt").write_text("different contents")
        self.data["entries"][URN].append({"version": "1.0.0", "uri": mirror.as_uri()})
        self.save_registry()
        with self.assertRaisesRegex(ResolutionError, "conflicting local package contents"):
            resolve_package(URN, self.registry)

    def test_relocation_preserves_identity_and_plan(self):
        selected = resolve_package(ACTION, self.registry)
        moved = self.root / "moved package"
        shutil.move(self.package, moved)
        self.data["entries"][URN][0]["uri"] = moved.as_uri()
        self.save_registry()
        relocated = resolve_package(ACTION, self.registry, digest=selected.digest)
        self.assertEqual(selected.plan(), relocated.plan())
        self.assertEqual(relocated.path, moved)

    def test_file_locations_never_drop_query_or_fragment(self):
        for suffix in ["?version=1", "#actions/hello", "?", "#", "%00", "%0a", "%FF"]:
            with self.subTest(suffix=suffix), self.assertRaises(ResolutionError):
                uri_to_path(self.package.as_uri() + suffix)
        with self.assertRaises(ResolutionError):
            uri_to_path("file://remote/tmp/package")
        self.assertEqual(uri_to_path("file://localhost" + str(self.package)), self.package)

    def test_read_only_resolution_and_unknown_action_do_not_execute(self):
        with patch("paxlet.runtime.subprocess.run", side_effect=AssertionError("executed")):
            for cmd in [("resolve", ACTION), ("resolve", URN, "--local"), ("inspect", ACTION)]:
                status, out, err = self.cli(*cmd)
                self.assertEqual(status, 0, err)
                self.assertTrue(json.loads(out))
            status, _, err = self.cli("invoke", ALIAS + "/actions/unknown")
            self.assertEqual(status, 2)
            self.assertIn("action not found", err)
            status, _, err = self.cli("invoke", ALIAS)
            self.assertEqual(status, 2)
            self.assertIn("explicit action", err)
        self.assertFalse((self.package / ".paxlet").exists())

    def test_registry_selection_is_not_shadowed_by_store(self):
        with patch("paxlet.store.get_package", side_effect=AssertionError("unverified store lookup")):
            status, _, err = self.cli("inspect", URN)
            self.assertEqual(status, 0, err)

    def test_runtime_rechecks_pin_before_executing(self):
        selected = resolve_package(ACTION, self.registry)
        (self.package / "new.txt").write_text("changed after planning")
        with patch("paxlet.runtime.subprocess.run", side_effect=AssertionError("executed")):
            with self.assertRaisesRegex(RuntimeError, "digest changed"):
                run_action(selected.path, "hello", {}, expected_digest=selected.digest, write_receipts=False)

    def test_receipt_keeps_pre_execution_digest_when_action_changes_files(self):
        (self.package / "hello.py").write_text(
            "from pathlib import Path\nimport json\nPath('result.txt').write_text('created')\nprint(json.dumps({'message':'done'}))\n")
        selected = resolve_package(ACTION, self.registry)
        _, receipt, _ = run_action(selected.path, selected.action, {"name": "Ada"}, expected_digest=selected.digest, write_receipts=False)
        self.assertEqual(receipt["package_digest"], selected.digest)
        self.assertNotEqual(package_digest(self.package), selected.digest)

    def test_inventory_can_describe_unsupported_transport_without_fetching(self):
        self.data["entries"][URN] = [{"version": "1.0.0", "uri": "https://mirror.example/pkg"}]
        self.save_registry()
        self.assertEqual(len(resolve(URN, self.registry)), 1)
        with self.assertRaisesRegex(ResolutionError, "no executable file"):
            resolve_package(URN, self.registry)

    def test_invalid_registry_shape_and_missing_package_fail_cleanly(self):
        for data in [[], {"registry": "paxlet/0.1", "entries": {URN: {}}},
                     {"registry": "paxlet/0.1", "entries": {URN: [None]}},
                     {"registry": "paxlet/0.1", "entries": {URN: []}}]:
            with self.subTest(data=data):
                self.registry.write_text(json.dumps(data))
                with self.assertRaises(ResolutionError):
                    resolve_package(URN, self.registry)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "source"
        shutil.copytree(ROOT / "examples/hello", self.package)
        self.store = self.root / "store"
        self.env = patch.dict("os.environ", {"PAXLET_STORE_DIR": str(self.store)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def put(self, source=None, **kwargs):
        from paxlet.store import put_package
        return put_package(source or self.package, **kwargs)

    def test_directory_archive_roundtrip_and_derived_catalog(self):
        from paxlet.packing import pack
        from paxlet.store import get_package, list_packages
        (self.package / ".paxlet").mkdir()
        (self.package / ".paxlet/receipt.json").write_text('{"private":"local"}')
        (self.package / "__pycache__").mkdir()
        (self.package / "__pycache__/cache.pyc").write_bytes(b"local cache")
        expected = package_digest(self.package)
        # Generated archives inside a source directory are not package members.
        source_archive = pack(self.package, self.package / "hello.paxlet.zip")
        self.assertEqual(package_digest(self.package), expected)
        digest, archive, path = self.put(expected_digest=expected)
        self.assertEqual(digest, expected)
        self.assertFalse((path / ".paxlet").exists())
        self.assertFalse((path / "__pycache__").exists())
        self.assertFalse((path / "PAXLET-METADATA.json").exists())
        self.assertEqual(package_digest(path), expected)
        with patch.dict("os.environ", {"PAXLET_STORE_DIR": str(self.root / "replica")}):
            imported, replica_archive, replica = self.put(source_archive, expected_digest=digest)
            self.assertEqual(imported, digest)
            self.assertEqual(archive.read_bytes(), replica_archive.read_bytes())
            self.assertEqual(get_package(digest), replica)
            records = list_packages()
            self.assertEqual(records[0]["actions"], json.loads((path / "paxlet.json").read_text())["actions"])
            self.assertEqual(records[0]["digest"], expected)
            self.assertFalse((self.root / "replica/index").exists())

    def test_reads_do_not_create_store_or_follow_legacy_indexes(self):
        from paxlet.store import get_package, has_package, list_packages
        self.assertEqual(list_packages(), [])
        self.assertIsNone(get_package(URN))
        self.assertFalse(has_package("sha256:" + "0" * 64))
        self.assertFalse(self.store.exists())
        legacy = self.store / "index"
        legacy.mkdir(parents=True)
        record = legacy / "old.json"
        record.write_text(json.dumps({"urn": URN, "path": str(self.package)}))
        original = record.read_bytes()
        self.assertIsNone(get_package(URN))
        self.put()
        self.assertEqual(record.read_bytes(), original)

    def test_invalid_digest_cannot_escape_store(self):
        from paxlet.store import get_package, has_package
        for value in ["../source", "sha256:../source", "A" * 64, "x" * 64, "", None]:
            for lookup in [get_package, has_package]:
                with self.subTest(value=value, lookup=lookup), self.assertRaises(ResolutionError):
                    lookup(value)
        self.assertFalse(self.store.exists())

    def test_bad_pin_publishes_nothing(self):
        from paxlet.store import list_packages
        with self.assertRaisesRegex(ResolutionError, "installation pin"):
            self.put(expected_digest="sha256:" + "0" * 64)
        self.assertEqual(list_packages(), [])

    def test_corrupt_payload_archive_and_partial_object_are_rejected(self):
        from paxlet.store import get_package, list_packages
        digest, archive, path = self.put()
        script = path / "hello.py"
        original = script.read_bytes()
        script.chmod(0o644)
        script.write_text("print('tampered')")
        for operation in [lambda: get_package(digest), list_packages, self.put]:
            with self.assertRaisesRegex(ResolutionError, "digest mismatch"):
                operation()
        script.write_bytes(original)
        archive.chmod(0o644)
        archive.write_bytes(b"not a zip")
        with self.assertRaisesRegex(ResolutionError, "invalid Paxlet archive"):
            get_package(digest)
        archive.unlink()
        with self.assertRaisesRegex(ResolutionError, "incomplete"):
            get_package(digest)

    def test_conflicting_claims_need_digest_and_versions_are_explicit(self):
        from paxlet.store import get_package, list_packages
        first, _, original = self.put()
        (self.package / "additional.txt").write_text("different content, same identity")
        second, _, _ = self.put()
        self.assertNotEqual(first, second)
        for version in [None, "1.0.0"]:
            with self.assertRaisesRegex(ResolutionError, "ambiguous"):
                get_package(URN, version=version)
        self.assertEqual(get_package(first), original)
        manifest_file = self.package / "paxlet.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["identity"]["version"] = "2.0.0"
        manifest_file.write_text(json.dumps(manifest))
        third, _, selected = self.put()
        self.assertEqual(get_package(URN, version="2.0.0"), selected)
        self.assertIsNone(get_package(URN, version="3.0.0"))
        self.assertEqual(len(list_packages()), 3)
        with self.assertRaisesRegex(ResolutionError, "version mismatch"):
            get_package(third, version="1.0.0")

    def test_interrupted_publish_is_invisible_and_retry_is_idempotent(self):
        from paxlet.store import list_packages
        rename = Path.rename
        def interruption(path, target):
            if path.name == "object":
                raise OSError("injected interrupted publication")
            return rename(path, target)
        with patch.object(Path, "rename", interruption):
            with self.assertRaisesRegex(ResolutionError, "interrupted publication"):
                self.put()
        self.assertEqual(list_packages(), [])
        # Crash leftovers from a killed process are not an installed inventory.
        abandoned = self.store / "objects-v1/.staging-crashed/package"
        abandoned.mkdir(parents=True)
        (abandoned / "paxlet.json").write_text("partial")
        first = self.put()
        self.assertEqual(self.put(), first)
        self.assertEqual(len(list_packages()), 1)
        self.assertTrue(abandoned.exists())

    def test_concurrent_process_imports_converge_on_one_object(self):
        import os
        import subprocess
        import sys
        from paxlet.store import list_packages
        processes = [subprocess.Popen(
            [sys.executable, "-m", "paxlet", "store", "put", str(self.package), "--json"],
            cwd=ROOT, env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        ) for _ in range(4)]
        outputs = []
        try:
            for process in processes:
                out, err = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, err)
                outputs.append(json.loads(out))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertTrue(all(value == outputs[0] for value in outputs))
        self.assertEqual(len(list_packages()), 1)

    def test_execution_copy_preserves_pin_and_keeps_receipts_out_of_store(self):
        from paxlet.store import get_package, materialize_package
        (self.package / "hello.py").write_text(
            "import json\nfrom pathlib import Path\nPath('result.txt').write_text('done')\nprint(json.dumps({'message':'done'}))\n")
        digest, _, installed = self.put()
        with patch("paxlet.runtime.subprocess.run", side_effect=AssertionError("executed")):
            with self.assertRaisesRegex(RuntimeError, "execution copy"):
                run_action(installed, "hello", {})
        target = self.root / "run-001"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["store", "get", digest, "--output-dir", str(target)]), 0)
        self.assertEqual(package_digest(target), digest)
        output, receipt, receipt_path = run_action(target, "hello", {"name": "Ada"}, expected_digest=digest)
        self.assertEqual(output, {"message": "done"})
        self.assertEqual(receipt["package_digest"], digest)
        self.assertTrue(receipt_path.is_relative_to(target))
        self.assertTrue((target / "result.txt").exists())
        self.assertFalse((installed / "result.txt").exists())
        self.assertFalse((installed / ".paxlet").exists())
        self.assertEqual(get_package(digest), installed)
        for destination in [target, self.store / "execution"]:
            with self.assertRaisesRegex(ResolutionError, "new and outside"):
                materialize_package(digest, destination)

    def test_archive_rejects_unsafe_duplicate_and_special_entries(self):
        import stat
        import warnings
        import zipfile
        from paxlet.packing import pack
        from paxlet.store import list_packages
        valid = pack(self.package, self.root / "valid.paxlet.zip")
        cases = ["../escaped", "/escaped", "C:/escaped", "folder\\escaped", "folder//file", "./hello.py",
                 "hello.py", "HELLO.py", "PAXLET-METADATA.json", "CON.txt", "trailing.", "dir/", "bad\nfile",
                 "a/" * 32 + "x", "a" * 1025]
        for name in cases:
            with self.subTest(name=name):
                bad = self.root / "bad.paxlet.zip"
                shutil.copyfile(valid, bad)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    with zipfile.ZipFile(bad, "a") as archive:
                        archive.writestr(name, "bad")
                with self.assertRaises(ResolutionError):
                    self.put(bad)
                self.assertEqual(list_packages(), [])
        for mode in [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o644]:
            shutil.copyfile(valid, bad)
            with zipfile.ZipFile(bad, "a") as archive:
                info = zipfile.ZipInfo("special")
                info.create_system = 3
                info.external_attr = mode << 16
                archive.writestr(info, "../escaped")
            with self.assertRaisesRegex(ResolutionError, "regular files"):
                self.put(bad)
        self.assertFalse((self.store / "escaped").exists())

    def test_archive_envelope_and_excluded_files_cannot_change_meaning(self):
        import zipfile
        from paxlet.packing import pack
        from paxlet.store import list_packages
        valid = pack(self.package, self.root / "valid.paxlet.zip")
        with zipfile.ZipFile(valid) as archive:
            members = [(item, archive.read(item)) for item in archive.infolist()]
        for change in ["pin", "identity", "missing", "duplicate-key", "invalid-manifest", "state"]:
            with self.subTest(change=change):
                bad = self.root / "bad.paxlet.zip"
                with zipfile.ZipFile(bad, "w") as archive:
                    for item, data in members:
                        if item.filename == "PAXLET-METADATA.json":
                            metadata = json.loads(data)
                            if change == "missing":
                                continue
                            if change == "pin":
                                metadata["package_digest"] = "sha256:" + "0" * 64
                            if change == "identity":
                                metadata["identity"]["version"] = "wrong"
                            data = json.dumps(metadata).encode()
                            if change == "duplicate-key":
                                data = data[:-1] + b', "format":"paxlet-archive/0.1"}'
                        if item.filename == "paxlet.json" and change == "invalid-manifest":
                            data = b'{}'
                        archive.writestr(item, data)
                    if change == "state":
                        archive.writestr(".paxlet/receipt.json", "{}")
                from paxlet.errors import PaxletError
                with self.assertRaises(PaxletError):
                    self.put(bad)
                self.assertEqual(list_packages(), [])

    def test_oversized_archive_is_rejected_before_extraction(self):
        from paxlet.packing import pack
        from paxlet.store import list_packages
        archive = pack(self.package, self.root / "valid.paxlet.zip")
        for constant, value in [("MAX_FILES", 1), ("MAX_FILE_BYTES", 8), ("MAX_PACKAGE_BYTES", 8), ("MAX_ARCHIVE_BYTES", 8)]:
            with self.subTest(limit=constant), patch("paxlet.store." + constant, value):
                with self.assertRaisesRegex(ResolutionError, "limit"):
                    self.put(archive)
            self.assertEqual(list_packages(), [])

    def test_symlink_store_paths_and_packages_are_rejected(self):
        from paxlet.errors import PaxletError
        from paxlet.store import get_package
        self.store.symlink_to(self.package, target_is_directory=True)
        with self.assertRaisesRegex(ResolutionError, "symlink"):
            self.put()
        self.store.unlink()
        (self.package / "link").symlink_to(self.package / "hello.py")
        with self.assertRaises(PaxletError):
            self.put()
        (self.package / "link").unlink()
        digest, _, installed = self.put()
        installed.chmod(0o755)
        (installed / "link").symlink_to(self.package / "hello.py")
        with self.assertRaises(PaxletError):
            get_package(digest)

    def vector_package(self):
        fixture = self.root / "vector"
        fixture.mkdir()
        files = {
            "paxlet.json": b'{"paxlet":"0.1","identity":{"urn":"urn:paxlet:test:vector","name":"vector","version":"1.0.0"},"resources":["data"]}\n',
            "data/a.txt": b"abc\n",
            "data/żółć.txt": "Zażółć gęślą jaźń\n".encode(),
            "data/\ue000.txt": b"private-use\n",
            "data/🚀.bin": bytes([0, 255, 10]),
        }
        for name, content in reversed(list(files.items())):
            file = fixture / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
        return fixture

    def test_canonical_digest_golden_vector_survives_archive_and_metadata(self):
        import os
        from paxlet.packing import pack
        fixture = self.vector_package()
        expected = "sha256:fad4aab122965054922d2c281824b6d7c0c987ddec3099a6f370e13dd2be76a5"
        self.assertEqual(package_digest(fixture), expected)
        (fixture / "data/a.txt").chmod(0o755)
        os.utime(fixture / "data/a.txt", (123, 123))
        self.assertEqual(package_digest(fixture), expected)
        archive = pack(fixture, self.root / "vector.paxlet.zip")
        digest, _, installed = self.put(archive, expected_digest=expected)
        self.assertEqual(digest, expected)
        self.assertEqual(package_digest(installed), expected)
        self.assertTrue((installed / "data/a.txt").stat().st_mode & 0o111)

    @unittest.skipUnless(shutil.which("node"), "Node required for independent digest implementation")
    def test_node_matches_digest_vector_including_non_bmp_sort_order(self):
        import subprocess
        fixture = self.vector_package()
        # JS default UTF-16 ordering differs from the contract for U+E000/U+1F680.
        script = r'''
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = process.argv[1];
const names = [];
function walk(dir, prefix = '') {
  for (const item of fs.readdirSync(dir, {withFileTypes:true})) {
    const name = prefix + item.name;
    if (item.isDirectory()) walk(path.join(dir, item.name), name + '/');
    else names.push(name);
  }
}
walk(root);
names.sort((a,b) => Buffer.compare(Buffer.from(a, 'utf8'), Buffer.from(b, 'utf8')));
const digest = crypto.createHash('sha256');
for (const name of names) {
  const relative = Buffer.from(name, 'utf8');
  const data = fs.readFileSync(path.join(root, name));
  const n = Buffer.alloc(4); n.writeUInt32BE(relative.length);
  const size = Buffer.alloc(8); size.writeBigUInt64BE(BigInt(data.length));
  digest.update(n).update(relative).update(size).update(data);
}
process.stdout.write('sha256:' + digest.digest('hex'));
'''
        result = subprocess.run(["node", "-e", script, str(fixture)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "sha256:fad4aab122965054922d2c281824b6d7c0c987ddec3099a6f370e13dd2be76a5")
        self.assertEqual(result.stdout, package_digest(fixture))

    def test_manifest_duplicates_and_malformed_shapes_fail_without_publication(self):
        from paxlet.errors import PaxletError
        from paxlet.store import list_packages
        target = self.package / "paxlet.json"
        original = json.loads(target.read_text())
        values = [b'\xff', b'{"paxlet":"0.1","paxlet":"0.1"}', b'[]']
        values.append(json.dumps({**original, "non_json_number": float("nan")}).encode())
        for key, value in [("permissions", []), ("actions", []), ("identity", None)]:
            changed = dict(original)
            changed[key] = value
            values.append(json.dumps(changed).encode())
        for value in values:
            with self.subTest(value=value[:60]):
                target.write_bytes(value)
                with self.assertRaises(PaxletError):
                    self.put()
                self.assertEqual(list_packages(), [])

    def test_materialization_remains_bound_to_selected_object_after_lookup(self):
        from paxlet.store import materialize_package, get_package
        digest, _, installed = self.put()
        def changed_after_lookup(*args, **kwargs):
            selected = get_package(*args, **kwargs)
            script = selected / "hello.py"
            script.chmod(0o644)
            script.write_text("print('different bytes')")
            return selected
        with patch("paxlet.store.get_package", side_effect=changed_after_lookup):
            with self.assertRaisesRegex(ResolutionError, "changed before materialization"):
                materialize_package(digest, self.root / "execution")
        self.assertFalse((self.root / "execution").exists())

    def test_source_change_during_installation_does_not_publish(self):
        from paxlet import store
        copy = store._copy_files
        def copy_changed(files, source, destination):
            (source / "hello.py").write_text("print('changed while copying')")
            copy(files, source, destination)
        with patch("paxlet.store._copy_files", side_effect=copy_changed):
            with self.assertRaisesRegex(ResolutionError, "source changed"):
                self.put()
        self.assertEqual(store.list_packages(), [])

    def test_archive_file_directory_collisions_are_rejected_before_publish(self):
        import zipfile
        from paxlet.packing import pack
        from paxlet.store import list_packages
        valid = pack(self.package, self.root / "valid.paxlet.zip")
        for names in [["parent", "parent/child"], ["Dir/a", "dir/b"], ["decomposed-e\u0301", "unused"]]:
            with self.subTest(names=names):
                bad = self.root / "bad.paxlet.zip"
                shutil.copyfile(valid, bad)
                with zipfile.ZipFile(bad, "a") as archive:
                    for name in names:
                        archive.writestr(name, "payload")
                with self.assertRaises(ResolutionError):
                    self.put(bad)
                self.assertEqual(list_packages(), [])
