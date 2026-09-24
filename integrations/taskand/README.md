# Taskand and Paxlet

Taskand owns discovery, grants, process activation and distributed execution.
Paxlet owns the portable package manifest, deterministic local resolution and
JSON action protocol. Neither a catalog entry nor a Paxlet binding grants
permission to invoke a Taskand process.

## Export a process without changing Taskand's package hash

```sh
python integrations/taskand/adapt.py ../taskand/generated/ --dry-run
python integrations/taskand/adapt.py ../taskand/generated/dev/chat/taskand.dev/v1/proc.yaml \
  --output-dir /tmp/taskand-chat-paxlet
python integrations/taskand/adapt.py ../taskand/generated/ \
  --output-dir /tmp/taskand-paxlets
```

Output directories must be new and outside the source tree. Exports copy the
process and its sibling modules, then validate and add `paxlet.json` to the copy.
The CLI refuses an in-place write. The legacy Python `adapt_proc_yaml(write=True)`
remains available for caller-owned staging directories only; `export_proc_yaml`
is the safe copying API. Invalid manifests are not written.

The adapter accepts the current Taskand profile
`proc://taskand.dev/<organism>/<capability>/vN`. It rejects missing/invalid URIs,
foreign authorities and conflicting organism declarations instead of inventing
an identity. The URI determines capability; a prose capability label cannot
rename the package. The original process URI remains a **package alias** and the
export contains the explicit action `run`.

Approve an environment registry mapping such as:

```json
{
  "registry": "paxlet/0.1",
  "aliases": {
    "proc://taskand.dev/dev/chat/v1": "urn:paxlet:taskand:dev:chat"
  },
  "entries": {
    "urn:paxlet:taskand:dev:chat": [
      {"version": "1.0.0", "uri": "file:/tmp/taskand-chat-paxlet"}
    ]
  }
}
```

`paxlet resolve proc://taskand.dev/dev/chat/v1 --local --registry registry.json`
verifies the exported package. Invoking it also requires an explicit `run` action
and a suitable execution environment. This is a local process execution, not a
call through Taskand's gateway and its authorization checks. The adapter's generic
object schemas and declared permissions do not establish runtime portability.

Do not replace a Taskand registry hash with a Paxlet digest: the algorithms and
file sets differ. Keep both provenance values during migration. See
[the ecosystem assessment](../../docs/taskand-lan.md) for observed boundaries,
LAN synchronization recommendations and remaining validation.
