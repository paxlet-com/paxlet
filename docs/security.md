# Security model

Paxlet Core uses one simple rule:

> **A Paxlet declares what it needs. A node decides what it gets.**

The manifest may declare filesystem, network and secret needs. Those declarations are requests, not grants.

## Reference runtime limitations

The tiny Python runtime is educational. It validates package paths and does not automatically expose arbitrary environment variables to child actions. A secret is passed only when:

1. it is declared in `permissions.secrets`;
2. the user passes `--allow-secret NAME`;
3. `NAME` exists in the caller environment.

The reference runtime does **not** provide kernel/container enforcement for filesystem and network permissions. Production Paxlet nodes should enforce those permissions with OS/container/VM sandboxing.

Receipts store secret **names only**, never values.
