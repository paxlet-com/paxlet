# Ticket 003: Adopt published Wellmanifest 0.20.52 for Paxlet CI

- **ID**: ticket-003
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-24

## Outcome

Pin Paxlet to published `wellmanifest/new-project` revision `980f6e5f73c923f2959c266b84de9ffc544671de` (release `v0.20.52`). The generated adopter workflow and reusable workflow now both install Wellman from the same canonical immutable `v<version>` tag. Keep the exact PR range for the managed gate.

## Acceptance criteria

- [x] AC-01: Goal check identified exactly four managed file changes and verified the published revision.
- [ ] AC-02: Managed gate and actual detached Paxlet CI workflow pass with the published 0.20.52 pin; revalidate product PR #2 after its merged changes are included in current main.
- [ ] AC-03: Publish a reviewable PR, pass required exact-head checks, and merge through independent Validator.

## Authorization and ownership

SESSION_EXECUTION_AUTHORIZATION: the user requested continued implementation, testing and protected merge. This continues the existing ticket-003 adoption scope; the user explicitly allowed the independent source corrective-release ticket, which is now merged and published as `v0.20.52`. This ticket remains disjoint from ticket-002 and restricted to its declared managed files plus the exact `tool.wellmanifest` metadata binding in `pyproject.toml`. The atomic-adoption checker explicitly binds that one packaging path to the published source revision; no other integration-owned setting is changed.

## Delivery boundary

Apply only the published immutable revision through Goal. Preserve target-owned manifest settings. Validate the adoption and replay the product CI gate at the updated main before protected delivery.
