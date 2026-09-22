#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = os.environ.get("PAXLET_CLI", f"{shlex.quote(sys.executable)} -m paxlet.cli")


def call(args, expect=0):
    command = shlex.split(CLI) + args
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(f"{' '.join(command)} returned {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def test(name, fn):
    try:
        fn()
        print(f"✓ {name}")
        return True
    except Exception as exc:
        print(f"✗ {name}: {exc}")
        return False


def main():
    checks = []
    checks.append(test("verify a valid Paxlet", lambda: call(["verify", "examples/hello", "--json"])))

    def inspect():
        r = call(["inspect", "examples/hello"])
        data = json.loads(r.stdout)
        assert data["identity"]["urn"] == "urn:paxlet:example:hello"
        assert "hello" in data["actions"]
    checks.append(test("inspect identity and actions", inspect))

    def run():
        r = call(["run", "examples/hello", "hello", "--input", '{"name":"Conformance"}', "--no-receipt"])
        assert json.loads(r.stdout)["message"] == "Hello, Conformance!"
    checks.append(test("JSON action protocol", run))

    def resolve():
        r = call(["resolve", "urn:paxlet:example:hello", "--registry", "registry/local.json"])
        data = json.loads(r.stdout)
        assert data["locations"][0]["uri"].startswith("file:")
    checks.append(test("URN resolves to a URI", resolve))

    checks.append(test("reject path traversal", lambda: call(["verify", "tests/fixtures/invalid-escape", "--json"], expect=1)))

    total = len(checks)
    passed = sum(checks)
    print(f"\nPaxlet Core 0.1 conformance: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
