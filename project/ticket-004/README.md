# Ticket 004: Add twinerd-core native paxlet capability package

- **ID**: ticket-004
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-27

## Outcome

Package native Twinerd Core Digital Twin and Virtualization capabilities as an addressable, verifiable Paxlet capability (`urn:paxlet:twinerd:core`).
Provides typed JSON schemas, cryptographic execution receipts, and deterministic actions (`inspect` and `benchmark`) enabling autonomous agents and MCP tool runners to execute zero-copy virtualization and system capability checks without an unrestricted shell.

## Acceptance criteria

- [x] AC-01: Create `examples/twinerd-core/paxlet.json` declaring `urn:paxlet:twinerd:core` @ `1.0.0` with `inspect` and `benchmark` actions.
- [x] AC-02: Create `examples/twinerd-core/adapter.py` connecting the JSON action protocol to the native `twinerd` binary with graceful host fallback.
- [x] AC-03: Validate package with `paxlet verify` and `paxlet inspect`.
- [x] AC-04: Verify execution and cryptographic receipt generation with `paxlet run`.
- [x] AC-05: Add automated unit test `test_twinerd_core_validates_and_inspects` to `tests/test_core.py`.
- [x] AC-06: Pass Wellmanifest governance verification (`./project/governance-check.sh`).
