# Ticket 002: Deterministic Paxlet action resolution and Taskand integration

- **ID**: ticket-002
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
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

- Host suite: 46 tests, 45 passed, PowerShell skipped on host; all 38 local
  Taskand generated process manifests validated with TASKAND_ROOT explicitly set.
- Docker: 46 tests, 45 passed, external Taskand catalog skipped; Bash, Python,
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
- Scope: 14 implementation files, three components, no new runtime dependencies.
- Recovery snapshots and command receipts: external local host state, not a claim
  of cross-machine durable or protected review evidence.

## Next action

Exact-commit validation of 19e91a0 passed. Validate and commit the development-stage
architecture revision, then retain the same ticket for any protected publication.
Taskand package/catalog replacement, staged replication and catalog sync
are separate follow-up slices described in docs/taskand-lan.md; no network-wide
synchronization or deployment is claimed by this ticket.

Architecture clarification validation: the full 46-test host suite passes with
one PowerShell skip already covered by the prior Docker run. The governed diff
check passes; no executable source changed in this continuation.
