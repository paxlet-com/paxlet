# Addressing packages and actions

A URN is a URI that names a resource. Paxlet distinguishes a package identity,
a package alias, an action selector and a transport location. URI syntax alone
does not authorize or trigger execution ([RFC 3986, §§1.1.3 and 1.2.2](https://www.rfc-editor.org/rfc/rfc3986.html)).
The following is Paxlet's application profile, not a claim of IANA registration.

| Value | Meaning |
|---|---|
| `urn:paxlet:example:hello` | Package identity in `identity.urn` |
| `paxlet://example/hello` | Package alias declared in `bindings` |
| `paxlet://example/hello/actions/hello?version=1.0.0` | Package alias, action and exact version selector |
| `file:///opt/paxlets/hello` | Environment-owned package location |

`bindings` contains stable package aliases, never action selectors. A manifest
claim does not register an alias. An environment administrator must approve an
exact alias → URN mapping; the resolver also checks that the selected manifest
declares that alias. There is no inferred URI → URN string replacement.

## Address profile

```text
paxlet://<authority>/<package>[/actions/<action>][?version=<exact-label>]
```

- Authority is a lowercase registry namespace, matching
  `[a-z0-9]+(?:[.-][a-z0-9]+)*`. It is not a host to contact; ports and userinfo
  are forbidden. Namespace ownership belongs to the configured registry.
- Package and action names match `[A-Za-z0-9][A-Za-z0-9._-]*` and are case sensitive.
  There is exactly one package segment; dot segments and empty names are rejected.
- Version is an exact opaque label matching `[A-Za-z0-9][A-Za-z0-9.+_-]*`, not
  a semver range. No implicit latest-version selection occurs.
- Percent encoding (including `%2F`, `%23`, `%252F` and encoded unreserved
  characters), fragments, trailing slashes and unknown/repeated query parameters
  are rejected in this initial profile. Even empty `?` and `#` are rejected.
- Other absolute package aliases such as Taskand's `proc://…/v1` may be registered
  explicitly. They have no implicit action; provide `run` separately. Query and
  fragment selectors are unsupported on these aliases and on URNs.

## Environment registry

Create a local JSON registry, separate from the package:

```json
{
  "registry": "paxlet/0.1",
  "aliases": {
    "paxlet://example/hello": "urn:paxlet:example:hello"
  },
  "entries": {
    "urn:paxlet:example:hello": [
      {"version": "1.0.0", "uri": "https://mirror.example/hello"},
      {"version": "1.0.0", "uri": "file:/opt/paxlets/hello"}
    ]
  }
}
```

Use a real local package location. Relative `file:` paths resolve against the
registry directory, including `file://localhost` paths. File URI query and
fragment components are rejected, not discarded. Package paths may contain
percent-encoded spaces. A location may additionally declare `digest` with a
`sha256:` prefix and 64 lowercase hexadecimal digits. Production registries
should pin it; it is the package digest, not the ZIP file checksum.

Duplicate JSON keys, alias chains, alias/entry conflicts and malformed records
fail closed. The optional `aliases` object keeps existing URN registries valid.
The repository's legacy `registry/local.json` remains an URN-only example;
use your environment registry for alias examples below.

## Resolve, inspect, invoke

```sh
# Inventory only: describes declared locations, including unsupported transports.
paxlet resolve urn:paxlet:example:hello --registry /path/to/registry.json

# Verify local content; an action URI implies --local.
paxlet resolve 'paxlet://example/hello/actions/hello?version=1.0.0' \
  --registry /path/to/registry.json
paxlet inspect paxlet://example/hello/actions/hello --registry /path/to/registry.json

# Execution is explicit. run and invoke are synonyms.
paxlet invoke 'paxlet://example/hello/actions/hello?version=1.0.0' \
  --registry /path/to/registry.json --input '{"name":"Ada"}'
paxlet run urn:paxlet:example:hello hello --version 1.0.0 \
  --registry /path/to/registry.json --input '{"name":"Ada"}'
```

Verified resolution returns `plan` with `package`, `action`, `version` and
`digest`, plus the selected local `path`. Persist the plan with input separately.
Replay by passing its package/action with `--version` and `--digest`; input stays
JSON, not URI query data. The runtime rechecks the digest before execution and
records that pre-execution digest in the receipt. Python callers use
`resolve_package(...).plan()` and `run_action(..., expected_digest=...)`.

Several advertised versions require an explicit version. Mirrors of a selected
version must agree on digest; accessible local copies are checked even when the
registry omitted hashes. Unsupported transports and missing paths are skipped.
Existing invalid manifests, identity/version mismatches, unknown actions and
integrity failures stop resolution rather than silently choosing another copy.
A request digest and a registry digest must agree. There is no disable-verification
mode (`resolve_to_path(..., verify_digest=False)` now raises an error).

`resolve` and `inspect` do not run package code, download packages or change
registries. Resolution no longer consults the mutable store index before the
registry. Use `paxlet store get …` to select a stored path explicitly, or register
its location with an exact version/digest. A package alias without an action
never implies a default action.

A digest pin detects changed content but is not publisher authentication or an
OS sandbox. The local reference runtime assumes its package directory is not
concurrently modified during invocation. Production nodes need read-only content
storage and their own execution grants. Package identity, location and execution
receipts can then evolve independently.

## Verified local content store

The store uses `$PAXLET_STORE_DIR/objects-v1/<sha256-hex>/`, with a `package/`
directory and a `package.paxlet.zip` archive inside each object. Without an
override, the root is `$PAXLET_HOME/store` (default `~/.paxlet/store`).
A private sibling staging directory is verified before one directory rename
publishes the object. Payload files are read-only; every lookup rechecks both
representations. Concurrent imports of the same digest converge on one object.
An interrupted import may leave `.staging-*` data, which inventory ignores.
No automatic garbage collection removes this recovery data.

```sh
paxlet store put ./examples/hello --json
# On a receiving node, supply the expected PACKAGE digest from its accepted plan:
paxlet store put ./hello.paxlet.zip --digest 'sha256:<64-lowercase-hex-digits>' --json
paxlet store list --json
paxlet store get urn:paxlet:example:hello --version 1.0.0 --output-dir ./run-001
paxlet invoke ./run-001 hello --digest 'sha256:<64-lowercase-hex-digits>' \
  --input '{"name":"Ada"}'
```

Substitute the actual digest returned by installation. Without `--output-dir`,
`store get` returns the verified storage path for inspection/transport. The
runtime rejects execution under the configured store root. An explicit new
execution copy keeps results, caches and receipts outside immutable content.
`--output-dir` never overwrites an existing directory. Python callers use
`put_package(source, expected_digest=...)`, `get_package(selector, version=...)`,
`materialize_package(selector, destination, version=...)`, and `list_packages()`.

There is no mutable Paxlet identity index. Inventory derives identity, version,
bindings, action definitions, dependencies and requested permissions from each
verified manifest. `path` and `archive` are local observations, not portable
catalog fields. Bindings remain claims; requested permissions are not grants.
Two objects claiming the same URN/version can coexist for review, but lookup by
that URN/version fails as ambiguous. Select a digest explicitly. The authorized
Taskand catalog must reject conflicting active assignments; storing bytes does
not activate an action or authorize an alias.

Legacy `archives/`, `packages/` and `index/` directories are preserved but are not
consulted by the new layout. Reinstall an original package/archive with a reviewed
digest to migrate it. There is no silent conversion of old index paths or old
Taskand hashes. Local filesystem owners can still change files/permissions;
read-only bits and digest checks are integrity controls, not a process sandbox.
Native Windows behavior and network filesystem crash semantics are not yet
validated by the Linux/PowerShell container tests.

### Inventory, archive and digest contract

The canonical inventory is the manifest plus local implementation/resources
selected by `collect_package_files`. Symlinks are forbidden. Unreferenced local
runtime/cache/build state is excluded, including `.paxlet/`, `.git/`,
`__pycache__/`, `node_modules/`, `build/`, `dist/`, `.pyc`, `.pyo` and generated
`.paxlet.zip` files. Installation copies this inventory, not the whole source
directory. Archive payloads must contain exactly that inventory.

`PAXLET-METADATA.json` is a reserved archive envelope. Its format, identity and
package digest must match the payload; it is removed before computing the package
digest and never becomes a package member. Duplicate entries/JSON fields, path
traversal, absolute paths, symlinks, special files, case aliases, file/directory
collisions, non-NFC paths, Windows device names and encrypted entries are rejected.
Archives contain files only; explicit directory entries are unsupported. Limits
are 10,000 payload paths (files and implied directories), 64 MiB per file,
256 MiB expanded data (including the envelope), 300 MiB compressed input and
1 MiB envelope. A path has at most 32 segments and 1,024 UTF-8 bytes. Manifest
JSON rejects duplicate keys and non-finite numbers, which are not portable JSON. Validation and installation
do not execute package code or fetch dependencies.

The package digest remains Core 0.1 SHA-256 over this concatenation for every
relative path sorted by Unicode scalar value (equivalently UTF-8 byte order):

```text
uint32_be(len(UTF8(path))) || UTF8(path) || uint64_be(len(content)) || content
```

Paths use `/`; lengths count bytes. Content includes the exact manifest bytes,
not reserialized JSON. Timestamps, executable bits and ZIP metadata are excluded.
Execution copies normalize modes to 0644/0755; stored files to 0444/0555.
The ZIP checksum and package digest are distinct contracts.

The executable golden vector in `tests/test_resolution.py` contains `a.txt`,
`żółć.txt`, U+E000 and U+1F680 paths, binary bytes and a fixed manifest. Its digest
is `sha256:fad4aab122965054922d2c281824b6d7c0c987ddec3099a6f370e13dd2be76a5`.
Independent Python and Node implementations must match it. In JavaScript use
UTF-8 `Buffer.compare` sorting; default UTF-16 string sorting fails this vector.
