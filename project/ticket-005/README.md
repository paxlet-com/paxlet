# Ticket 005: Add twinerd-vm native paxlet capability package for VM lifecycle

- **ID**: ticket-005
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-27

## Outcome

Package native Twinerd VM creation and lifecycle management as an addressable, verifiable Paxlet capability (`urn:paxlet:twinerd:vm`).
Enables autonomous agents and MCP orchestrators to create and tear down zero-copy CoW digital twin sandboxes in milliseconds with cryptographic receipts, virtual display allocation, and Tokio WebSocket gateway routing.

## Acceptance criteria

- [x] AC-01: Create `examples/twinerd-vm/paxlet.json` declaring `urn:paxlet:twinerd:vm` @ `1.0.0` with `create` and `destroy` actions.
- [x] AC-02: Create `examples/twinerd-vm/adapter.py` integrating with `twinerd create --json` and cleanup logic with host fallback.
- [x] AC-03: Validate package structure and manifest conformance with `paxlet` engine.
- [x] AC-04: Add automated unit test `test_twinerd_vm_validates_and_creates` to `tests/test_core.py`.
- [x] AC-05: Pass Wellmanifest governance verification (`./project/governance-check.sh`).
