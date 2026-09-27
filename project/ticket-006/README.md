# Ticket 006: Implementacja pakietu urn:paxlet:twinerd:backup z deterministyczna migawka CoW

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-09-27

## Goal and scope

Implement dedicated Paxlet capability urn:paxlet:twinerd:backup for deterministic snapshot creation and compressed archive exports with verifiable execution receipts.

## Acceptance criteria

- [x] AC-01: Implementacja `examples/twinerd-backup/paxlet.json`.
- [x] AC-02: Implementacja `examples/twinerd-backup/adapter.py`.
- [x] AC-03: Zgodność z kontraktem wykonania `paxlet/0.1`.
- [x] AC-04: Testy jednostkowe w `tests/test_twinerd_backup.py` zakończone sukcesem.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

