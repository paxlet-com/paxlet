# paxlet


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.3-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$0.07-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-1.9h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $0.0714 (3 commits)
- 👤 **Human dev:** ~$190 (1.9h @ $100/h, 30min dedup)

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

## Important security note

The reference runtime is intentionally educational. It validates package paths and exposes secrets only after explicit user grant, but it **does not enforce filesystem/network permissions with an OS sandbox**. Production nodes should use containers, VMs or OS policy for enforcement. See `docs/security.md`.

## Status

Core 0.1 is a draft intended to make the idea testable and implementable by independent runtimes. See `ROADMAP.md`.


## License

Licensed under Apache-2.0.
