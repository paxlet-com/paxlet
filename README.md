# paxlet


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.4-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$0.08-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-2.0h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $0.0849 (4 commits)
- 👤 **Human dev:** ~$200 (2.0h @ $100/h, 30min dedup)

Generated on 2026-09-22 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

**Build small. Connect everything.**

Paxlet Core is a deliberately small contract for packaging **resources and actions** as addressable capabilities.

A Paxlet has a stable identity, a version, clear inputs/outputs, explicit dependencies and requested permissions. A node can resolve it, verify it, run it and produce a receipt.

```text
URN identity
    │
    ▼
┌──────────── Paxlet ────────────┐
│ resources                     │
│ actions                       │
│ dependencies                  │
│ permissions                   │
│ provenance                    │
└───────────────────────────────┘
    │
    ▼
URI locations → Node → Receipt
```

## Start in five minutes

Requires Python 3.11+ and no third-party runtime dependencies. You can run it directly after cloning:

```bash
./bin/paxlet init /tmp/my-first
./bin/paxlet run /tmp/my-first hello --input '{"name":"Ada"}'

./bin/paxlet verify examples/hello
./bin/paxlet run examples/hello hello --input '{"name":"Ada"}'
```

Optional developer install:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

Or address the same capability by identity:

```bash
./bin/paxlet resolve urn:paxlet:example:hello
./bin/paxlet run urn:paxlet:example:hello hello --input '{"name":"Ada"}'
```

Try a science-oriented example:

```bash
./bin/paxlet run examples/science-fasta-gc analyze --input '{}'
./bin/paxlet run examples/statistics-mean mean --input '{"values":[1,2,4,8]}'
```

## CLI

```text
paxlet init    DIRECTORY
paxlet verify  PATH|URN
paxlet inspect PATH|URN
paxlet resolve URN
paxlet run     PATH|URN ACTION --input JSON
paxlet pack    PATH|URN -o package.paxlet.zip
```

## Why Core is small

Paxlet is not an AI-agent framework. It is the portable unit that larger systems can use.

```text
Paxlet Core      package + identity + contract
Paxlet Node      resolution + grants + execution + receipts
Paxlet Network   registries + peers + distribution
Taskand          planning + orchestration + adaptive-system showcase
```

Taskand can demonstrate planners, processes, federation, mesh, Digital Twin, MCP, governance and recovery without making those features mandatory for every Paxlet implementation.

## Repository map

```text
SPEC.md                 normative Core 0.1 draft
schemas/                manifest + receipt schemas
paxlet/                 tiny Python reference runtime
examples/               five understandable capabilities
registry/local.json     local URN → URI resolver example
conformance/            implementation compatibility runner
docs/                   addressing, security, receipts, layers
integrations/taskand/    how Taskand fits as the showcase
```

## Conformance

```bash
python -m unittest discover -s tests -v
python conformance/run.py
```

## Governance and standard updates

The adopted wellmanifest/new-project contract is pinned in
`.governance/manifest.lock.json`. Its managed files are verified by the local
commit hook; the hook does not fetch or install a new standard. Explicit updates
use Goal's published-release verifier in the adoption ticket's linked worktree:

```bash
goal governance adopt --standard-repository /path/to/wellmanifest/new-project \
  --source-revision 42dce766825f35b2a97cf16c9bf72e80a4a0c2d3 \
  --target-root /path/to/adoption-worktree --check
# After admission and a bounded write lease, apply the reviewed plan with --upgrade.
```

This adoption uses published standard 0.20.50. Its CI workflow obtains the matching
governance runtime from the standard's `wellman-v0.20.50` release tag, rather than
assuming the same version exists on PyPI. Run CI validation with the `ci` actor;
local hook installation is a developer-clone check. The separately installed
fleet CLI and this versioned gate runtime share the `wellman` command name and
must not be confused. Use an isolated environment for the CI runtime.

The local adoption inventory records only evidenced **S2 local conformance**:
the normative schema, deterministic checker, immutable revision and managed file
digests. It does not claim required CI checks (S3) or branch protection (S4).
`standard_pack_check.py --strict` intentionally continues to report the unmet
baseline requirements. A passing local `wellman check` alone is insufficient.

The host's hourly `wellmanifest-sync` timer currently runs in read-only **plan**
mode. An inventory entry allows it to identify this pin and report drift; it does
not automatically allocate a ticket, update a repository, push or merge. Legacy
`updates.trigger=pre-commit` metadata does not enable automatic updates in the
current hook. Treat `unmanaged`, failed scans and missing release evidence as
findings, not successful freshness checks.

Audit on 2026-09-24 found no GitHub ruleset or `main` branch protection in Paxlet,
Taskand or the ecosystem tests repository. Their baseline pack records were empty,
and tests PR #7 failed to provision `wellman==0.20.43` before validation. The
Taskand standard pin was 0.20.16, versus 0.20.43 in Paxlet/tests. This change fixes
Paxlet's checked-in runtime provisioning and inventory declaration; the other
repositories and hosted settings retain their separately owned work.

Full proactive enforcement still needs a controlled update executor consuming the
inventory, independent review/required checks, protected branch settings and actual
delivery receipts. Keep those gaps visible until their deployed behavior is tested.
Local validation, a successful timer exit and an `enforce` label in a manifest do
not establish that end-to-end result.

## Important security note

The reference runtime is intentionally educational. It validates package paths and exposes secrets only after explicit user grant, but it **does not enforce filesystem/network permissions with an OS sandbox**. Production nodes should use containers, VMs or OS policy for enforcement. See `docs/security.md`.

## Status

Core 0.1 is a draft intended to make the idea testable and implementable by independent runtimes. See `ROADMAP.md`.


## License

Licensed under Apache-2.0.
