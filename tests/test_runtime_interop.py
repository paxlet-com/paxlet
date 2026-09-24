"""Same package/action contract across Python, Bash and PowerShell runners."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from paxlet.manifest import package_digest
from paxlet.resolver import resolve_package
from paxlet.runtime import run_action


class RuntimeInteropTests(unittest.TestCase):
    def execute(self, tool, argv, script_name, script):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = root / "package"
            package.mkdir()
            (package / script_name).write_text(script)
            manifest = {
                "paxlet": "0.1", "identity": {"urn": "urn:paxlet:interop:hello", "name": "hello", "version": "1.0.0"},
                "bindings": ["paxlet://interop/hello"],
                "actions": {"hello": {"runtime": {"type": "command", "argv": argv},
                                      "input": {"type": "object"}, "output": {"type": "object"}}},
                "permissions": {"host_tools": [tool]}}
            (package / "paxlet.json").write_text(json.dumps(manifest))
            digest = package_digest(package)
            registry = root / "registry.json"
            registry.write_text(json.dumps({"registry": "paxlet/0.1", "aliases": {"paxlet://interop/hello": manifest["identity"]["urn"]},
                "entries": {manifest["identity"]["urn"]: [{"version": "1.0.0", "digest": digest, "uri": package.as_uri()}]}}))
            selected = resolve_package("paxlet://interop/hello/actions/hello", registry)
            output, receipt, _ = run_action(selected.path, selected.action, {"name": "Ada"},
                                           expected_digest=selected.digest, write_receipts=False)
            self.assertEqual(output, {"message": "Hello, Ada!"})
            self.assertEqual(receipt["package_digest"], digest)
            self.assertEqual(receipt["action"], "hello")
            return output

    def test_python_contract(self):
        self.execute("python3", ["python3", "hello.py"], "hello.py",
                     "import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'message': 'Hello, '+p['name']+'!'}))\n")

    @unittest.skipUnless(shutil.which("bash"), "Bash is not installed")
    def test_bash_contract(self):
        # JSON parsing belongs to a declared runtime tool, not shell interpolation.
        import shlex
        self.execute("bash", ["bash", "hello.sh"], "hello.sh",
                     "exec " + shlex.quote(sys.executable) + " -c \"import json,sys; p=json.load(sys.stdin); print(json.dumps({'message':'Hello, '+p['name']+'!'}))\"\n")

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is covered by tests/docker/Dockerfile")
    def test_powershell_contract(self):
        self.execute("pwsh", ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", "hello.ps1"], "hello.ps1",
                     "$ErrorActionPreference = 'Stop'\n$p = [Console]::In.ReadToEnd() | ConvertFrom-Json\n"
                     "@{ message = 'Hello, ' + $p.name + '!' } | ConvertTo-Json -Compress\n")
