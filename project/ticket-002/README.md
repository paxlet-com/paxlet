# Ticket 002: Deterministic Paxlet action resolution and Taskand integration

- **ID**: ticket-002
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-24
- **Session bound**: maxActiveMinutes=120; checkpointMinutes=30
- **Queue**: PLF-002 (primary checkout Planfile)

## Authorization and scope

SESSION_EXECUTION_AUTHORIZATION: user requested implementation starting with Paxlet,
using package-level bindings, explicit action addresses, deterministic resolution,
and an ecosystem assessment of Taskand LAN propagation, replication and sync.
Application scope is disjoint from governance ticket-001 / PLF-001, preserved.
Work-start admitted a new application ticket; allocator owns the canonical
worktree ticket-002--action-resolution and its revision-1/fence-1 lease.

## Acceptance criteria

- [x] AC-01: Registry-controlled aliases and strict package/action URI profile;
  reject ambiguous names, encoding, fragments and unknown query parameters.
- [x] AC-02: Verify manifest identity, exact version, action and content digest;
  skip unsupported/unavailable locations without bypassing integrity failures.
- [x] AC-03: Resolve/inspect never execute; explicit invocation returns receipts;
  resolved plans expose identity, action, version and digest for replay.
- [x] AC-04: Regression tests cover URN/URI equivalence, conflicts, fallback,
  tampering, relocation and read-only resolution; run stack and governance gates.
- [x] AC-05: Inspect current Taskand and nl-dsl-sh code and document integration
  gaps and a bounded LAN simplification/migration plan with evidence.
- [x] AC-06: Revise the ecosystem architecture for development-stage breaking
  changes; remove mandatory legacy compatibility and specify a single package,
  digest, invocation and catalog model with ordered implementation slices.

- [x] AC-07: Directory/archive installations have identical canonical digests;
  bounded safe extraction, staged atomic publication and verified reuse prevent
  partial/corrupt objects from becoming available. Preserve legacy store data.
- [x] AC-08: Derive package/action catalog records from verified manifests, require
  digest selection for conflicting contents, separate writable execution copies,
  and validate actual Taskand consumption plus cross-runtime digest vectors.

## Implementation continuation (2026-09-24)

SESSION_EXECUTION_AUTHORIZATION: user requested continuation. Resume the same
application ticket and fenced worktree. Implement the package/store slice within
paxlet/** and existing test/document paths. Store objects carry bytes only; mutable
identity assignments, aliases, grants and synchronization remain Taskand catalog
responsibilities. No second mutable identity database is introduced in Paxlet.

## Development-stage clarification (2026-09-24)

SESSION_EXECUTION_AUTHORIZATION: the user clarified that Taskand, Paxlet and related
projects are development versions and deeper architectural changes are allowed.
Compatibility with existing proc URIs, manifest layouts, hashing and registry
storage is not an acceptance requirement for the forthcoming architecture.
Continue this ticket's documentation scope and update PLF-003; each future source
slice still belongs to its owning repository/ticket. Existing artifacts, data and
concurrent work are preserved; the clarification does not authorize silent data
loss or treating local checks as protected merge evidence.

## Non-goals

No changes to Taskand or nl-dsl-sh repositories in this slice. No implicit network
execution, peer trust, automatic activation, remote artifact fetching, release,
or migration of existing governance work. Publication requires declared protected
review and delivery; local checks do not grant merge authority.

## Validation

`python3 -m unittest discover -s tests -v`, `python3 conformance/run.py`,
`make verify-examples`, `./project/governance-check.sh`.

## Delivery evidence

- Host suite: 66 tests, 65 passed, PowerShell skipped on host; all 38 local
  Taskand generated process manifests validated with TASKAND_ROOT explicitly set.
- Docker: 66 tests, 64 passed, external Taskand catalog/consumer skipped; Bash, Python,
  PowerShell and isolated Node export executed successfully with network disabled.
- Core conformance: 5/5; all five example packages verify.
- Actual nl-dsl-sh Bash+Python plan compiled/exported/resolved/executed successfully;
  receipt pinned the package digest. Source remains untouched.
- Full worktree diff governance passes with explicit origin/main base. Default
  base inference selects historical ticket-001 (accepted base 0c199ca) and reports
  GOV-BASE-002; that unrelated carrier remains unchanged. Before publication use
  the required exact range `--base origin/main --head HEAD`.
- No data migration is performed: aliases are an optional resolver input/interface;
  existing registries and Taskand state are not rewritten.
- Scope: 15 implementation files, three components, no new runtime dependencies.
- Recovery snapshots and command receipts: external local host state, not a claim
  of cross-machine durable or protected review evidence.

- AC-07/AC-08: canonical directory/archive digest equality, atomic object publication,
  independent Python/Node golden vector, unsafe/oversized archive rejection,
  corruption detection, four-process imports and interrupted-install recovery pass.
- Actual Taskand export → Paxlet store → writable copy → run succeeds with an
  unchanged digest and receipt outside the store. Taskand's own 14 shell-workflow
  tests also pass against this Paxlet source; no Taskand source was changed.
- Taskand independently advanced to 41268dd during this session (ticket-050 gossip).
  Inspected changed modules and ran mocked, network-free probes of four concrete
  sync/authentication issues; details are in docs/taskand-lan.md. Shell/federation
  consumer source is unchanged from the original assessment head.
- Planfile MCP update failed with a terminated session; the bounded update was
  preserved externally in planfile-outbox.json, then delivered through the installed
  Planfile CLI to PLF-002/PLF-003. No GitHub adapter is configured.

## Next action

Commit the validated store slice, then retain this ticket for any protected
publication. The next Taskand slice must observe the owner/controller of merged
ticket-050 and current work-start admission before modifying its new gossip worker.
Reuse that worker for the common catalog/store; do not build a competing daemon.
The latest assessment identifies automatic approval, credential forwarding,
missing admin-grant checks, bounds, revisions and withdrawal handling as follow-ups.


GOV-ARCHITECTURE-001 was a classification error in prose `dataChanges`: the
changed persistent layout is the core's private content cache, not Taskand catalog
storage or a migration. Per the local runbook it now uses an explicit
`component-local-state` record bound to core. No existing data is rewritten;
archive format paxlet-archive/0.1 and ownership remain unchanged. Import validation
and derived read APIs are implementation/interface changes, not data transfers.

## Publication continuation (2026-09-24)

SESSION_EXECUTION_AUTHORIZATION: the user requested continued implementation,
testing and merge, then continuation after governance PR1 landed. Resume this
existing ticket and preserve its earlier implementation evidence. The previous
writer stopped with a clean checkout; a real controller lease now binds this
session after owner/process, checkpoint, intent and HEAD observations. Original
unpublished history is retained in an external Git bundle.

The candidate is rebased onto independently approved main
`1ae249e4dd0ea4439a01fcbd50c51a577838d17f`, inheriting its published standard
0.20.50 and corrected CI runtime. No managed governance source is authored here.
Revalidate the package/action/store behavior and actual Taskand consumer, then
freeze the candidate through independent review and controller merge.

- [ ] AC-09: Publish this candidate, pass all required checks and obtain a trusted
  exact-head approval plus controller merge receipt. Close through external
  terminal evidence; no repository closure commit or product deployment.

Publication revalidation on the approved base: host suite 66 run / 65 passed /
PowerShell skipped; offline non-root Docker suite 66 run / 64 passed / two
external Taskand tests skipped. These environments jointly execute all 66 tests.
Bash, PowerShell, Python and the independent Node digest vector pass. Current
Taskand main `4a2334119919139a73eb52f79a6425e462c8ca9f` passes the real
export/store/execution-copy test and its own 14 shell-workflow tests with this
Paxlet candidate. Core conformance passes 5/5, all five examples verify, and the
managed exact-base gate passes. Test logs and the prior Git bundle are preserved
in the external publication evidence directory. LAN/network convergence and
production deployment remain outside this package delivery.
