# Paxlet, Taskand and LAN synchronization

Assessment date: 2026-09-24. This slice implements Paxlet addressing and isolated
Taskand export. It does not implement LAN discovery, replication or a Taskand
upgrade. Observations below distinguish implemented behavior from recommendations.

## Observed ecosystem

Taskand was inspected at commit
[`1046dbd`](https://github.com/paxlet-com/taskand/tree/1046dbdabad3fd857aa33291474f4a546dd16009).
The local `nl-dsl-sh` source is not a Git checkout; inspected
`src/nl_dsl_sh/interop.py` SHA-256 is
`4f2f5196e0d1fb1ccaa99afcf24f0ecf5e14928a50fb08e51aa449f55fd948cc`.

| Boundary | Evidence and consequence |
|---|---|
| Taskand catalog and pull | `generated/registry/core/taskand.dev/v1/federation.mjs` exports active entries, compares advertised/payload hashes, rejects same-URI content conflicts and registers imports as candidates. These are useful primitives to retain. |
| Peer visualization | `gateway/handlers/mesh.py` explicitly reports configured peers as `UNOBSERVED`. It neither probes peers nor verifies identity or remote execution. This is not functioning LAN discovery. |
| Process addressing | `generated/registry/core/taskand.dev/v1/store.mjs` accepts only `proc://taskand.dev/<organism>/<capability>/vN` and derives a package directory from that URI. Endpoint address, node identity and process identity need separate records. |
| Node identity | The same `store.mjs` uses `TASKAND_NODE` or hostname as `NODE_ID`. That is a label, not a verified durable cryptographic identity. Paxlet receipt node strings also do not establish authenticated identity. |
| Package hash | Taskand's `package.mjs` hashes sorted direct files with NUL delimiters. Paxlet includes the manifest and recursive package closure with length framing. Both use SHA-256 but produce different digests. Adding `paxlet.json` to a live Taskand package invalidates its existing hash. |
| Install boundary | Federation writes directly into the final directory before verifying, then deletes on failure. Directory existence checks and registration are separate from installation. Interrupted and concurrent imports need a staging/commit boundary. |
| Mutable control state | `store.mjs` already locks and atomically renames organism registries. Preserve that protection. Peer/genome writes have a separate path. `lifecycle.mjs` permits refresh of builtin hashes; that local development operation must not become a distributed immutable-version overwrite. |
| Export from nl-dsl-sh | `interop.py::export_paxlet` exports a compiled Python wrapper, resources, explicit permissions and `run`; it currently has no Paxlet action-URI planning adapter. Its wrapper returns `{exit_code, stdout, stderr}`. |
| Permissions and portability | Paxlet's reference runtime does not enforce filesystem/network declarations. Taskand's adapter uses generic object schemas and detects Node/Python/shell entry points; validation alone does not prove a process can run outside Taskand's environment. |

## What now works in Paxlet

The environment registry explicitly binds package aliases to URNs. Action URI
resolution verifies manifest identity/version, alias declaration, action and
package digest before returning a portable selection. Moving an installed package
changes a registry location, not its manifest. Execution rechecks the selected
digest and preserves it in the receipt. `resolve`/`inspect` do not execute code.

Taskand export copies packages into a new directory. It does not modify, activate
or grant access to the source process. A `proc://` alias denotes the copied package;
`run` remains explicit. A future Taskand gateway adapter must apply the existing
caller grants before any remote invocation. Calling the local Paxlet runtime
is not equivalent to passing through that gateway.

## Recommended simplifications in Taskand

These are proposed next slices, not deployed behavior.

1. **Use one catalog contract with separate identities.** Keep process URI,
   canonical package URN/version/digest, node ID and endpoint locations distinct.
   Feed CLI, gateway, MCP and mesh views from that catalog projection. Preserve
   the existing `proc://` identifiers during migration; do not mechanically
   replace them with `paxlet://` strings. Approve alias mappings at the registry
   boundary, never from package self-declarations alone.
2. **Start with one seed peer and pull reconciliation.** Allow a configured LAN
   endpoint and bounded polling. Add optional mDNS/DNS-SD announcements only to
   discover candidate endpoints. Discovery must not distribute execution grants,
   bearer tokens or implicitly trusted package aliases. Validate peer endpoints,
   redirects, response schemas, timeouts and size limits before fetching content.
   Separate read-only catalog access from authenticated package transfer/calls.
3. **Replicate immutable content by digest.** Retain catalog → missing content →
   verify → candidate, but fetch only absent digests. Stage files in a new
   directory, reject traversal/symlinks/oversized payloads, verify the complete
   closure and atomically publish under a content-addressed path. Serialize the
   final install and catalog update. Interrupted downloads must never expose a
   partially installed package; an identical retry must converge.
4. **Synchronize catalog revisions, not whole runtime directories.** Start with
   bounded snapshots carrying an origin, revision and digest, plus conditional
   reads. Add deltas only when snapshot size justifies them. Reject a different
   digest for the same immutable identity/version and preserve explicit removal
   markers to prevent deleted entries returning from an old peer. Keep peer
   health/TTL observations separate from package metadata and activation policy.
   A single writer per catalog namespace is simpler than initial multi-writer
   conflict resolution. Do not replicate `.env`, grants, secrets, locks or local
   execution queues together with package bytes.
5. **Keep invocation and replication independently retryable.** An immutable
   download can be retried after observation. A process call may have side
   effects: persist a caller-scoped invocation ID bound to action, package digest
   and input digest, record receipts at the execution node and reconcile unknown
   outcomes before retrying. Do not promise exactly-once effects without a
   transactional boundary in the called service.

For a small LAN, this means a node service, a durable content store and a catalog
with one controlled writer per namespace. Existing process modules can remain;
there is no need to make every package operate an independent network registry.

## Migration order and acceptance checks

| Slice | Bounded change | Required evidence |
|---|---|---|
| Paxlet (this ticket) | Explicit aliases/actions, digest pins, copy-based export | URN/URI equivalence, malformed selectors, fallback, conflicts, relocation and non-execution tests |
| Taskand catalog bridge | Map approved process URI to Paxlet package plus `run`; retain original Taskand hash as typed provenance | Old proc callers keep their behavior; export does not change the registered source; unauthorized calls still fail |
| Taskand replication | Stage and verify immutable content, then atomically install and register candidates | Two isolated nodes; interrupted transfer, concurrent import, tampering, malicious paths, idempotent retry and same-version conflict |
| Taskand LAN sync | Seed configuration, catalog revisions, peer liveness; discovery optional | Three nodes; offline/rejoin, stale snapshot, removed entry, untrusted peer and convergent inventories without automatic activation |
| nl-dsl-sh planner bridge | Consume verified selections and persist package/action/version/digest/input | Alias remapping cannot silently change a saved plan; digest and action checks precede runtime selection |
| Authorized remote invoke | Keep Taskand grants and reconcile invocation receipts | Timeout after acceptance does not cause a blind duplicate execution |

The two-node and three-node checks remain required before describing the combined
system as proven for LAN synchronization. This Paxlet slice supplies the package
selection boundary; it does not establish Taskand's network guarantees.

## Validation and reproduction

```sh
TASKAND_ROOT=/path/to/taskand python3 -m unittest discover -s tests -v
python3 conformance/run.py
make verify-examples

# Bash/Python/PowerShell contract tests, with no network access during the run.
docker build -f tests/docker/Dockerfile -t paxlet-interop .
docker run --rm --network none --read-only --tmpfs /tmp:rw,mode=1777 \
  --mount type=bind,src="$PWD",dst=/workspace,readonly paxlet-interop
```

The host adapter check validated all 38 processes in the inspected Taskand
`generated/` tree without writing to it. A controlled exported Node fixture
executed through the explicit registry alias with digest-bound receipt. This
establishes the adapter boundary, not portability of all 38 production processes.

An actual local nl-dsl-sh plan containing a Bash step and a Python step was compiled,
exported to Paxlet, resolved by URN with a digest, and executed successfully. The
output was `Hello, Ada!` followed by `Python complete`. No Taskand process or
nl-dsl-sh source was modified. Bash and PowerShell alternatives share the same
JSON action contract in `tests/test_runtime_interop.py`; their runtime-specific
packages intentionally have different content digests.
