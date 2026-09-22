# Paxlet Core 0.1 — Draft Specification

**Status:** experimental draft

## 1. Purpose

A **Paxlet** is a versioned, addressable package of **resources and actions** with explicit dependencies, capabilities and provenance.

Core 0.1 deliberately does **not** define planners, agents, LLMs, organisms, federation algorithms or self-healing. Those are systems that can be built *with* Paxlets.

## 2. Mental model

```text
identity + package + contract
            │
            ├── resources
            ├── actions
            ├── dependencies
            ├── permissions
            └── provenance
```

A developer should be able to understand one Paxlet without understanding the network around it.

## 3. Manifest

Every unpacked Paxlet MUST contain `paxlet.json` at its root.

Required fields:

- `paxlet`: MUST equal `"0.1"`.
- `identity.urn`: stable logical identity, starting with `urn:paxlet:`.
- `identity.name`: human-readable local name.
- `identity.version`: version of this package instance.

A Paxlet MUST expose at least one action or resource.

## 4. Identity and location

`identity.urn` answers **what is this capability?**

A binding URI answers **where/how can this instance be reached?**

The stable identity and its locations MUST NOT be treated as the same field.

Example:

```text
urn:paxlet:science:fasta-gc
    ├── file:///lab/paxlets/fasta-gc
    └── https://lab.example/paxlets/fasta-gc
```

Version is separate from the stable URN in Core 0.1.

## 5. Actions

Actions are named operations. The Core 0.1 process protocol is deliberately small:

1. runtime receives one JSON value on stdin;
2. successful runtime writes exactly one JSON value to stdout;
3. diagnostics go to stderr;
4. exit code `0` means success.

The reference runtime supports:

- `runtime.type = "python"` with a relative `entry` file;
- `runtime.type = "command"` with an `argv` array.

`input` and `output` use a small JSON-Schema-like subset: `type`, `properties`, `required`, and `items`.

## 6. Resources

`resources` is a list of relative package paths. Paths MUST remain inside the package root. A node MUST reject manifest paths that escape the package root.

## 7. Dependencies

`requires` is a list of stable Paxlet URNs.

Core 0.1 defines declaration and discovery only. It does not define a dependency solver or automatic orchestration.

## 8. Permissions

A Paxlet declares what it needs; the **node decides what it gets**.

Core fields:

```json
{
  "permissions": {
    "filesystem": {"read": [], "write": []},
    "network": [],
    "secrets": []
  }
}
```

A manifest declaration is not itself authority. Runtime implementations are responsible for enforcing grants.

## 9. Receipts

A node SHOULD produce a receipt for each action execution. A receipt binds at least:

- Paxlet URN and version;
- package digest;
- action;
- input/output digests;
- runtime and node identity;
- start/finish timestamps;
- exit code.

Secret values MUST NOT appear in receipts.

## 10. Package digest

The reference digest is SHA-256 over a deterministic sequence of package file names and bytes for the manifest, action entries and declared resources.

## 11. Archives

Portable archives use `.paxlet.zip` in Core 0.1. The archive contains the original package files plus `PAXLET-METADATA.json` with identity and package digest.

## 12. Conformance

A conforming Core 0.1 CLI SHOULD provide equivalent operations to:

```text
verify <package>
inspect <package>
run <package> <action> --input JSON
resolve <URN>
pack <package>
```

The repository `conformance/` suite exercises this behavioural surface.

## 13. Non-goals for Core 0.1

The following are intentionally higher layers:

- LLM planning;
- goal decomposition;
- organism generation;
- federation policy;
- mesh replication;
- evolutionary admission;
- healing;
- distributed scheduling.

Taskand demonstrates several of those possibilities while Paxlet Core stays small enough to implement independently.
