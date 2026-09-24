# Ticket 001: Adopt wellmanifest standards

- **ID**: ticket-001
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-22

## Goal

Adopt wellmanifest/wellman baseline standards (new-project, git-lifecycle, worktrees, ticket-lifecycle, merge, validation-attestation, logs, docs).

## Acceptance criteria

- [x] Immutable adoption lock generated at 0.20.43 (56223848ea416d59e53123cdcab6e9155a11fe2b).
- [x] Standard requirements registered in .governance/standard-requirements.json.
- [x] Worktree and git lifecycle guards active (.worktrees, worktree-guard.yaml, .githooks/pre-commit).
- [x] Wellman check passes cleanly.

## Continuation: PLF-004 (2026-09-24)

SESSION_EXECUTION_AUTHORIZATION: user asks whether proactive wellmanifest/wellman
standardization works and requests continued project work. Reuse this matching
adoption ticket. Its initial material baseline is already on main; no active
governance writer, controller lease or PR was observed. A canonical linked
checkout isolates the refresh from existing product tickets.

- Session bound: maxActiveMinutes=120; checkpointMinutes=30.
- [x] AC-05: Apply only the verified published standard revision through Goal;
  preserve target settings and use its corrected runtime provisioning/CI actor.
- [x] AC-06: Register the actual local pin/artifact evidence so the read-only
  update inventory detects this adopter; do not fabricate protected compliance.
- [x] AC-07: Reproduce local, strict-pack and CI-runtime results; document actual
  timer behavior, missing remote protection and the controlled next actions.

Existing acceptance checks above describe the original local baseline only. They
do not assert automatic freshness, full pack adoption or server-side enforcement.
No source, test or publication changes are made in Taskand, tests or the upstream
standards repositories by this continuation. PLF-003 remains queued/in progress.

## Local validation and remaining delivery

Goal verified the published 0.20.50 revision
`42dce766825f35b2a97cf16c9bf72e80a4a0c2d3`; an adoption recheck reports up-to-date.
The package's governance metadata now matches that lock. The managed local gate
and isolated 0.20.50 runtime with `--actor ci` pass against the explicit accepted
base and changed paths. Paxlet runtime tests pass 20/20; Core conformance passes
5/5. Exact committed-head results are retained in the external delivery ledger.

Strict baseline-pack validation still reports eight unmet requirements: the
new-project record is evidenced only to S2, and seven other required pack records
are missing. No artifact digest errors occur. The inventory probe recognizes this
linked checkout as managed and up-to-date. This does not change the primary
checkout observed by the hourly plan-only timer until delivery is integrated.

Remaining ecosystem work: refresh the separately owned Taskand/tests adoptions,
connect the update inventory to an authorized executor and independent Validator,
then verify required CI and branch protection from outside the product checkout.
Tests PR #7 remains open with its pre-validation runtime-installation failure.
No remote publication, protected-policy change or merge is part of this local
continuation. The ticket stays IN_PROGRESS pending independent delivery.

## Publication continuation (2026-09-24)

SESSION_EXECUTION_AUTHORIZATION: the user explicitly requests "kontynuuj, scal".
This extends the earlier local preparation to branch push, PR publication and
protected merge after independent exact-head approval. The earlier local-only
boundary is superseded for this delivery; deployment and protected policy changes
remain separate. Keep this ticket IN_PROGRESS / PUBLICATION until the protected
controller records its terminal receipt.

The deployed Validator preflight currently returns PUBLICATION_PROFILE_MISSING
for paxlet-com/paxlet. Publish the concrete candidate and verify CI while retaining
that prerequisite; never replace the protected merge path with a direct merge.

- [ ] AC-08: Publish this candidate and obtain an exact-head independent review
  and protected-controller merge receipt; verify remote state before cleanup.
