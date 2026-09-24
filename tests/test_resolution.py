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
